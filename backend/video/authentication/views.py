import random
from django.shortcuts import render
from rest_framework import status, views, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url
from users.serializers import UserCreateSerializer

User = get_user_model()


class RegisterView(views.APIView):
    """用户注册视图"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CaptchaView(views.APIView):
    """生成验证码视图"""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        hashkey = CaptchaStore.generate_key()
        image_url = captcha_image_url(hashkey)
        return Response({
            'hashkey': hashkey,
            'image_url': request.build_absolute_uri(image_url)
        })


class LoginView(views.APIView):
    """用户登录视图"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        captcha_key = request.data.get('captcha_key')
        captcha_value = request.data.get('captcha_value')
        
        if not username or not password:
            return Response({'detail': '请输入用户名和密码'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查登录失败次数
        cache_key = f"login_fail_{username}"
        fail_count = cache.get(cache_key, 0)
        
        # 如果失败次数 >= 3，强制校验验证码
        if fail_count >= 3:
            if not captcha_key or not captcha_value:
                return Response({
                    'detail': '请输入验证码',
                    'show_captcha': True
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 校验验证码
            try:
                captcha = CaptchaStore.objects.get(hashkey=captcha_key)
                if captcha.response.lower() != captcha_value.lower():
                    return Response({
                        'detail': '验证码错误',
                        'show_captcha': True
                    }, status=status.HTTP_400_BAD_REQUEST)
                captcha.delete()  # 验证码只能使用一次
            except CaptchaStore.DoesNotExist:
                return Response({
                    'detail': '验证码已过期',
                    'show_captcha': True
                }, status=status.HTTP_400_BAD_REQUEST)

        try:
            if '@' in username:
                user = User.objects.get(email=username)
            else:
                user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户不存在也增加失败次数，防止暴力破解
            cache.set(cache_key, fail_count + 1, 600)  # 10分钟有效期
            return Response({
                'detail': '用户名或密码错误',
                'show_captcha': (fail_count + 1 >= 3)
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if not user.is_active:
            return Response({'detail': '账号已被禁用，请联系管理员'}, status=status.HTTP_403_FORBIDDEN)
        
        if not user.check_password(password):
            cache.set(cache_key, fail_count + 1, 600)
            return Response({
                'detail': '用户名或密码错误',
                'show_captcha': (fail_count + 1 >= 3)
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # 登录成功，清除失败次数
        cache.delete(cache_key)
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
        })


class LogoutView(views.APIView):
    """用户登出视图 - 将 refresh token 加入黑名单"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()  # 将 token 加入黑名单
            return Response({'detail': '成功登出'}, status=status.HTTP_200_OK)
        except TokenError:
            # token 无效或已过期，但仍然返回成功（用户体验）
            return Response({'detail': '成功登出'}, status=status.HTTP_200_OK)
