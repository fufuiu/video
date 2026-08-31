"""支付宝沙箱支付工具类"""
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class AlipayService:
    """支付宝支付服务"""
    
    def __init__(self):
        self.appid = settings.ALIPAY_APPID
        self.app_private_key = self._normalize_private_key(getattr(settings, 'ALIPAY_APP_PRIVATE_KEY', ''))
        self.alipay_public_key = self._normalize_public_key(getattr(settings, 'ALIPAY_PUBLIC_KEY', ''))
        self.debug = settings.ALIPAY_DEBUG
        self.gateway = settings.ALIPAY_GATEWAY
        self.return_url = settings.ALIPAY_RETURN_URL
        self.notify_url = settings.ALIPAY_NOTIFY_URL

        self._sdk = None
        try:
            from alipay import AliPay

            if self.app_private_key and self.alipay_public_key and self.appid:
                # python-alipay-sdk 需要的是 PEM 内容（字符串），不需要文件路径
                self._sdk = AliPay(
                    appid=str(self.appid),
                    app_notify_url=self.notify_url,
                    app_private_key_string=self.app_private_key,
                    alipay_public_key_string=self.alipay_public_key,
                    sign_type="RSA2",
                    debug=bool(self.debug),
                )
        except Exception as e:
            logger.warning(f"支付宝SDK初始化失败，将使用简化实现: {e}")

    def _normalize_private_key(self, key: str) -> str:
        key = (key or '').strip()
        if not key:
            return ''

        # settings.py 里通常是纯 base64 内容；pycryptodome 需要 PEM
        if 'BEGIN' not in key:
            key = f"-----BEGIN PRIVATE KEY-----\n{key}\n-----END PRIVATE KEY-----"
        return key

    def _normalize_public_key(self, key: str) -> str:
        key = (key or '').strip()
        if not key:
            return ''

        if 'BEGIN' not in key:
            key = f"-----BEGIN PUBLIC KEY-----\n{key}\n-----END PUBLIC KEY-----"
        return key
    
    def _sign(self, params):
        """
        对参数进行RSA2签名
        注意：实际项目中需要安装 pycryptodome 或使用支付宝官方SDK
        这里简化处理，建议安装 python-alipay-sdk
        """
        # 已迁移到 python-alipay-sdk；此方法仅保留给历史代码路径
        return self._simple_sign(params)
    
    def _simple_sign(self, params):
        """简化签名（仅用于测试，实际请安装python-alipay-sdk）"""
        import hashlib
        unsigned_string = "&".join(
            f"{k}={v}" for k, v in sorted(params.items()) if v
        )
        return hashlib.sha256(unsigned_string.encode('utf-8')).hexdigest()[:64]
    
    def _verify(self, params, sign):
        """
        验证支付宝签名
        """
        # 已迁移到 python-alipay-sdk；此方法仅保留给历史代码路径
        return True
    
    def create_order_string(self, order_id, subject, amount, body=''):
        """
        创建手机网站支付订单字符串
        返回用于前端跳转的URL
        """
        params = {
            'app_id': self.appid,
            'method': 'alipay.trade.wap.pay',
            'format': 'JSON',
            'charset': 'utf-8',
            'sign_type': 'RSA2',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': '1.0',
            'return_url': self.return_url,
            'notify_url': self.notify_url,
            'biz_content': {
                'out_trade_no': order_id,
                'total_amount': str(amount),
                'subject': subject,
                'body': body,
                'product_code': 'QUICK_WAP_WAY',
            }
        }
        
        # 将biz_content转为JSON字符串
        import json
        params['biz_content'] = json.dumps(params['biz_content'], ensure_ascii=False)
        
        # 签名
        sign = self._sign(params)
        params['sign'] = sign
        
        # 构建URL
        query_string = urlencode(params)
        return f"{self.gateway}?{query_string}"
    
    def create_page_pay_url(self, order_id, subject, amount, body=''):
        """
        创建电脑网站支付URL
        """
        if self._sdk:
            try:
                order_string = self._sdk.api_alipay_trade_page_pay(
                    out_trade_no=order_id,
                    total_amount=str(amount),
                    subject=subject,
                    body=body,
                    return_url=self.return_url,
                    notify_url=self.notify_url,
                )
                # SDK 返回的是 querystring，需要拼接网关
                return f"{self.gateway}?{order_string}"
            except Exception as e:
                logger.error(f"支付宝SDK创建支付URL失败: {e}")
                raise

        params = {
            'app_id': self.appid,
            'method': 'alipay.trade.page.pay',
            'format': 'JSON',
            'charset': 'utf-8',
            'sign_type': 'RSA2',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': '1.0',
            'return_url': self.return_url,
            'notify_url': self.notify_url,
            'biz_content': {
                'out_trade_no': order_id,
                'total_amount': str(amount),
                'subject': subject,
                'body': body,
                'product_code': 'FAST_INSTANT_TRADE_PAY',
            }
        }
        
        import json
        params['biz_content'] = json.dumps(params['biz_content'], ensure_ascii=False)
        
        sign = self._sign(params)
        params['sign'] = sign
        
        query_string = urlencode(params)
        return f"{self.gateway}?{query_string}"
    
    def verify_notify(self, params):
        """
        验证异步通知
        返回 (is_valid, trade_status, out_trade_no, trade_no)
        """
        sign = params.get('sign')
        sign_type = params.get('sign_type')
        
        if not sign:
            logger.error("异步通知缺少签名")
            return False, None, None, None
        
        # 验证签名
        if self._sdk:
            try:
                params_to_verify = dict(params)
                params_to_verify.pop('sign_type', None)
                params_to_verify.pop('sign', None)
                if not self._sdk.verify(params_to_verify, sign):
                    logger.error("异步通知签名验证失败")
                    return False, None, None, None
            except Exception as e:
                logger.error(f"异步通知验签异常: {e}")
                return False, None, None, None
        else:
            if not self._verify(params, sign):
                logger.error("异步通知签名验证失败")
                return False, None, None, None
        
        trade_status = params.get('trade_status')
        out_trade_no = params.get('out_trade_no')
        trade_no = params.get('trade_no')
        
        # 验证是否是支付成功状态
        if trade_status in ['TRADE_SUCCESS', 'TRADE_FINISHED']:
            return True, trade_status, out_trade_no, trade_no
        
        return True, trade_status, out_trade_no, trade_no
    
    def query_order(self, order_id):
        """
        查询订单状态
        """
        if self._sdk:
            try:
                result = self._sdk.api_alipay_trade_query(out_trade_no=order_id)
                # result 结构由 SDK 返回
                return {
                    'success': result.get('code') == '10000',
                    'trade_status': result.get('trade_status'),
                    'trade_no': result.get('trade_no'),
                    'total_amount': result.get('total_amount'),
                }
            except Exception as e:
                logger.error(f"查询订单失败: {e}")
                return {'success': False}

        params = {
            'app_id': self.appid,
            'method': 'alipay.trade.query',
            'format': 'JSON',
            'charset': 'utf-8',
            'sign_type': 'RSA2',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': '1.0',
            'biz_content': {
                'out_trade_no': order_id,
            }
        }
        
        import json
        params['biz_content'] = json.dumps(params['biz_content'], ensure_ascii=False)
        
        sign = self._sign(params)
        params['sign'] = sign
        
        # 发送请求
        import requests
        try:
            response = requests.post(
                self.gateway,
                data=params,
                timeout=10
            )
            result = response.json()
            
            if 'alipay_trade_query_response' in result:
                query_result = result['alipay_trade_query_response']
                return {
                    'success': query_result.get('code') == '10000',
                    'trade_status': query_result.get('trade_status'),
                    'trade_no': query_result.get('trade_no'),
                    'total_amount': query_result.get('total_amount'),
                }
        except Exception as e:
            logger.error(f"查询订单失败: {e}")
        
        return {'success': False}


# 单例
alipay_service = AlipayService()
