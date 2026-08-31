from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from ..models import UserSettings, LoginDevice
from ..serializers import (
    UserSettingsSerializer, 
    LoginDeviceSerializer,
    BindPhoneSerializer,
    SendPhoneCodeSerializer
)

User = get_user_model()


class UserSettingsViewSet(viewsets.ViewSet):
    """用户综合设置视图集"""
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        """获取当前用户的所有设置"""
        user = request.user
        
        # 获取或创建用户设置
        settings, created = UserSettings.objects.get_or_create(user=user)
        serializer = UserSettingsSerializer(settings)
        
        return Response({
            'settings': serializer.data,
            'phone': user.phone or '',
            'email': user.email or ''
        })
    
    def update(self, request, pk=None):
        """更新用户设置"""
        user = request.user
        settings, created = UserSettings.objects.get_or_create(user=user)
        
        serializer = UserSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def privacy(self, request):
        """获取隐私设置"""
        user = request.user
        settings, _ = UserSettings.objects.get_or_create(user=user)
        
        return Response({
            'public_profile': settings.public_profile,
            'show_history': settings.show_history,
            'allow_messages': settings.allow_messages,
            'public_collections': settings.public_collections,
            'show_following': settings.show_following
        })
    
    @action(detail=False, methods=['put'])
    def update_privacy(self, request):
        """更新隐私设置"""
        user = request.user
        settings, _ = UserSettings.objects.get_or_create(user=user)
        
        # 只更新隐私相关字段
        privacy_fields = ['public_profile', 'show_history', 'allow_messages', 
                         'public_collections', 'show_following']
        for field in privacy_fields:
            if field in request.data:
                setattr(settings, field, request.data[field])
        settings.save()
        
        return Response({'detail': '隐私设置已更新'})
    
    @action(detail=False, methods=['get'])
    def playback(self, request):
        """获取播放设置"""
        user = request.user
        settings, _ = UserSettings.objects.get_or_create(user=user)
        
        return Response({
            'autoplay': settings.autoplay,
            'quality': settings.quality,
            'speed': settings.speed,
            'remember_volume': settings.remember_volume,
            'danmaku': settings.danmaku,
            'remember_progress': settings.remember_progress
        })
    
    @action(detail=False, methods=['put'])
    def update_playback(self, request):
        """更新播放设置"""
        user = request.user
        settings, _ = UserSettings.objects.get_or_create(user=user)
        
        playback_fields = ['autoplay', 'quality', 'speed', 'remember_volume', 
                          'danmaku', 'remember_progress']
        for field in playback_fields:
            if field in request.data:
                setattr(settings, field, request.data[field])
        settings.save()
        
        return Response({'detail': '播放设置已更新'})
    
    @action(detail=False, methods=['get'])
    def interface(self, request):
        """获取界面设置"""
        user = request.user
        settings, _ = UserSettings.objects.get_or_create(user=user)
        
        return Response({
            'dark_mode': settings.dark_mode,
            'layout': settings.layout,
            'page_size': settings.page_size,
            'hover_preview': settings.hover_preview
        })
    
    @action(detail=False, methods=['put'])
    def update_interface(self, request):
        """更新界面设置"""
        user = request.user
        settings, _ = UserSettings.objects.get_or_create(user=user)
        
        interface_fields = ['dark_mode', 'layout', 'page_size', 'hover_preview']
        for field in interface_fields:
            if field in request.data:
                setattr(settings, field, request.data[field])
        settings.save()
        
        return Response({'detail': '界面设置已更新'})


class LoginDeviceViewSet(viewsets.ViewSet):
    """登录设备管理视图集"""
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        """获取当前用户的所有登录设备"""
        devices = LoginDevice.objects.filter(user=request.user)
        serializer = LoginDeviceSerializer(devices, many=True)
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """移除指定设备"""
        try:
            device = LoginDevice.objects.get(pk=pk, user=request.user)
            if device.is_current:
                return Response(
                    {'detail': '无法移除当前设备'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            device.delete()
            return Response({'detail': '设备已移除'})
        except LoginDevice.DoesNotExist:
            return Response(
                {'detail': '设备不存在'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def remove_all(self, request):
        """移除所有其他设备"""
        count = LoginDevice.objects.filter(
            user=request.user, 
            is_current=False
        ).delete()[0]
        return Response({'detail': f'已移除 {count} 个设备'})


class BindPhoneViewSet(viewsets.ViewSet):
    """绑定手机视图集"""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def send_code(self, request):
        """发送手机验证码"""
        serializer = SendPhoneCodeSerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data['phone']
            
            # 检查手机号是否已被使用
            if User.objects.filter(phone=phone).exclude(id=request.user.id).exists():
                return Response(
                    {'phone': '该手机号已被其他用户绑定'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # TODO: 实际发送短信验证码
            # 这里暂时模拟发送成功
            # 实际项目中应该调用短信服务API
            
            return Response({'detail': '验证码已发送'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def bind(self, request):
        """绑定手机号"""
        serializer = BindPhoneSerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data['phone']
            code = serializer.validated_data['code']
            
            # 检查手机号是否已被使用
            if User.objects.filter(phone=phone).exclude(id=request.user.id).exists():
                return Response(
                    {'phone': '该手机号已被其他用户绑定'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # TODO: 验证验证码
            # 这里暂时跳过验证，实际项目中应该验证
            # if not verify_phone_code(phone, code):
            #     return Response({'code': '验证码错误'}, status=400)
            
            # 绑定手机号
            request.user.phone = phone
            request.user.save()
            
            return Response({'detail': '手机绑定成功'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def unbind(self, request):
        """解绑手机号"""
        if not request.user.phone:
            return Response(
                {'detail': '未绑定手机号'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # TODO: 验证用户身份（如密码或验证码）
        
        request.user.phone = None
        request.user.save()
        
        return Response({'detail': '手机已解绑'})
