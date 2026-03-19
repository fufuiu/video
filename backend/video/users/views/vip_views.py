"""
VIP充值支付视图
"""
import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from ..models import User, VIPOrder
from ..utils.alipay import alipay_service

logger = logging.getLogger(__name__)


# VIP套餐配置
VIP_PACKAGES = {
    'monthly': {'months': 1, 'discount': 1.0},
    'quarterly': {'months': 3, 'discount': 0.85},  # 85折
    'yearly': {'months': 12, 'discount': 0.7},  # 7折
}


def generate_order_id():
    """生成订单号"""
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    random_str = uuid.uuid4().hex[:8].upper()
    return f"VIP{timestamp}{random_str}"


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_vip_packages(request):
    """
    获取VIP套餐列表
    """
    prices = settings.VIP_PRICES[1]
    packages = [{
        'level': 1,
        'name': prices['name'],
        'prices': {
            'monthly': {
                'price': prices['monthly'],
                'original_price': prices['monthly'],
                'months': 1,
                'label': '月度会员'
            },
            'quarterly': {
                'price': round(prices['quarterly'], 2),
                'original_price': round(prices['monthly'] * 3, 2),
                'months': 3,
                'label': '季度会员',
                'discount': '省' + str(round(prices['monthly'] * 3 - prices['quarterly'], 2)) + '元'
            },
            'yearly': {
                'price': round(prices['yearly'], 2),
                'original_price': round(prices['monthly'] * 12, 2),
                'months': 12,
                'label': '年度会员',
                'discount': '省' + str(round(prices['monthly'] * 12 - prices['yearly'], 2)) + '元'
            }
        }
    }]
    
    return Response({
        'packages': packages,
        'current_vip': {
            'is_vip': request.user.is_vip,
            'vip_expire_time': request.user.vip_expire_time,
            'is_vip_active': request.user.is_vip_active,
        }
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_vip_orders(request):
    """
    获取VIP订单列表
    """
    orders = VIPOrder.objects.filter(user=request.user).order_by('-created_at')
    
    order_list = []
    for order in orders:
        order_list.append({
            'id': order.id,
            'order_id': order.order_id,
            'months': order.months,
            'amount': str(order.amount),
            'status': order.status,
            'status_display': order.get_status_display(),
            'payment_method': order.payment_method,
            'created_at': order.created_at,
            'paid_at': order.paid_at,
        })
    
    return Response({
        'orders': order_list
    })


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def create_vip_order(request):
    """
    创建VIP订单并发起支付
    """
    duration = request.data.get('duration')  # monthly, quarterly, yearly
    payment_method = request.data.get('payment_method', 'alipay')  # 默认支付宝
    
    # 参数验证
    if not duration:
        return Response(
            {'error': '缺少必要参数'},
            status=status.HTTP_400_BAD_REQUEST
        )

    vip_level = 1
    
    if duration not in VIP_PACKAGES:
        return Response(
            {'error': '无效的购买时长'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # 计算价格和月数
    package = VIP_PACKAGES[duration]
    price_config = settings.VIP_PRICES[vip_level]
    base_price = price_config[duration]
    months = package['months']
    
    # 创建订单
    order_id = generate_order_id()
    order = VIPOrder.objects.create(
        user=request.user,
        order_id=order_id,
        vip_level=vip_level,
        months=months,
        amount=Decimal(str(base_price)),
        payment_method=payment_method,
        status='pending'
    )
    
    logger.info(f"创建VIP订单: {order_id}, 用户: {request.user.username}, "
                f"等级: {vip_level}, 月数: {months}, 金额: {base_price}")
    
    # 发起支付宝支付
    try:
        vip_name = price_config['name']
        subject = f"{vip_name} - {months}个月"
        body = f"购买{vip_name}会员{months}个月"
        
        # 使用电脑网站支付
        pay_url = alipay_service.create_page_pay_url(
            order_id=order_id,
            subject=subject,
            amount=base_price,
            body=body
        )
        
        return Response({
            'order_id': order_id,
            'amount': str(base_price),
            'pay_url': pay_url,
            'message': '订单创建成功，请前往支付'
        })
    except Exception as e:
        logger.error(f"创建支付订单失败: {e}")
        order.status = 'cancelled'
        order.save()
        return Response(
            {'error': '创建支付订单失败'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([])  # 不需要认证，支付宝回调
@permission_classes([])  # 不需要权限
def alipay_notify(request):
    """
    支付宝异步通知回调
    """
    logger.info(f"收到支付宝异步通知: {request.data}")
    
    # 获取所有参数
    params = dict(request.data)
    
    # 验证签名
    is_valid, trade_status, out_trade_no, trade_no = alipay_service.verify_notify(params)
    
    if not is_valid:
        logger.error(f"支付宝异步通知验签失败: {out_trade_no}")
        return Response('fail', status=status.HTTP_400_BAD_REQUEST)
    
    if not out_trade_no:
        logger.error("支付宝异步通知缺少订单号")
        return Response('fail', status=status.HTTP_400_BAD_REQUEST)
    
    try:
        order = VIPOrder.objects.get(order_id=out_trade_no)
    except VIPOrder.DoesNotExist:
        logger.error(f"订单不存在: {out_trade_no}")
        return Response('fail', status=status.HTTP_404_NOT_FOUND)
    
    # 检查订单状态
    if order.status == 'paid':
        logger.info(f"订单已支付: {out_trade_no}")
        return Response('success')
    
    # 处理支付结果
    if trade_status in ['TRADE_SUCCESS', 'TRADE_FINISHED']:
        # 支付成功
        order.complete_payment()
        order.payment_method = 'alipay'
        order.save()
        
        logger.info(f"VIP订单支付成功: {out_trade_no}, 用户: {order.user.username}, "
                    f"等级: {order.vip_level}, 月数: {order.months}")
        
        # TODO: 发送通知给用户
        
        return Response('success')
    else:
        logger.warning(f"支付未成功: {out_trade_no}, 状态: {trade_status}")
        return Response('success')


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def check_order_status(request):
    """
    检查订单状态（前端轮询使用）
    """
    order_id = request.query_params.get('order_id')
    
    if not order_id:
        return Response(
            {'error': '缺少订单号'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        order = VIPOrder.objects.get(order_id=order_id, user=request.user)
    except VIPOrder.DoesNotExist:
        return Response(
            {'error': '订单不存在'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # 如果订单待支付，主动查询支付宝
    if order.status == 'pending':
        try:
            result = alipay_service.query_order(order_id)
            if result.get('success') and result.get('trade_status') in ['TRADE_SUCCESS', 'TRADE_FINISHED']:
                order.complete_payment()
                order.payment_method = 'alipay'
                order.save()
        except Exception as e:
            logger.error(f"查询订单状态失败: {e}")
    
    return Response({
        'order_id': order.order_id,
        'status': order.status,
        'status_display': order.get_status_display(),
        'vip_level': order.vip_level,
        'months': order.months,
        'amount': str(order.amount),
        'paid_at': order.paid_at,
        'user_vip_status': {
            'is_vip': order.user.is_vip,
            'vip_level': order.user.vip_level,
            'vip_expire_time': order.user.vip_expire_time,
            'is_vip_active': order.user.is_vip_active,
        }
    })


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def cancel_order(request):
    """
    取消订单
    """
    order_id = request.data.get('order_id')
    
    if not order_id:
        return Response(
            {'error': '缺少订单号'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        order = VIPOrder.objects.get(order_id=order_id, user=request.user)
    except VIPOrder.DoesNotExist:
        return Response(
            {'error': '订单不存在'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if order.status != 'pending':
        return Response(
            {'error': '只能取消待支付的订单'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    order.status = 'cancelled'
    order.save()
    
    return Response({
        'message': '订单已取消'
    })


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def dev_mark_order_paid(request):
    """开发环境：模拟支付成功（仅用于本地联调）"""
    if not getattr(settings, 'DEBUG', False):
        return Response(status=status.HTTP_404_NOT_FOUND)

    order_id = request.data.get('order_id')
    if not order_id:
        return Response(
            {'error': '缺少订单号'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        order = VIPOrder.objects.get(order_id=order_id, user=request.user)
    except VIPOrder.DoesNotExist:
        return Response(
            {'error': '订单不存在'},
            status=status.HTTP_404_NOT_FOUND
        )

    if order.status != 'pending':
        return Response(
            {'error': '只能模拟待支付的订单'},
            status=status.HTTP_400_BAD_REQUEST
        )

    order.complete_payment()
    order.payment_method = 'mock'
    order.save()

    return Response({
        'message': '模拟支付成功',
        'order_id': order.order_id,
        'status': order.status,
        'paid_at': order.paid_at,
    })
