from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views.dashboard_views import DashboardViewSet
from .views.notification_views import UserNotificationViewSet, NotificationSettingViewSet
from .views.comment_views import UserCommentViewSet
from .views.user_views import UserProfileView, UserViewSet
from .views.admin_user_views import UserManagementViewSet
from .views.statistics_views import StatisticsViewSet
from .views.system_views import SystemSettingsViewSet
from .views.admin_management_views import AdminManagementViewSet
from .views.log_views import SystemOperationLogViewSet
from .views.database_views import DatabaseManagementViewSet
from .views.permission_views import PermissionViewSet, RoleViewSet, UserPermissionViewSet
from .views.settings_views import UserSettingsViewSet, LoginDeviceViewSet, BindPhoneViewSet
from .views.vip_views import (
    get_vip_packages, get_vip_orders, create_vip_order,
    alipay_notify, check_order_status, cancel_order,
    dev_mark_order_paid
)


router = DefaultRouter()

router.register(r'notifications', UserNotificationViewSet, basename='notifications')
router.register(r'notification-settings', NotificationSettingViewSet, basename='notification-settings')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')
router.register(r'comments', UserCommentViewSet, basename='comments')
router.register(r'admin-users', UserManagementViewSet, basename='admin-users')
router.register(r'admins', AdminManagementViewSet, basename='admins')
router.register(r'statistics', StatisticsViewSet, basename='statistics')
router.register(r'system', SystemSettingsViewSet, basename='system')
router.register(r'logs', SystemOperationLogViewSet, basename='logs')
router.register(r'database', DatabaseManagementViewSet, basename='database')
router.register(r'permissions', PermissionViewSet, basename='permissions')
router.register(r'roles', RoleViewSet, basename='roles')
router.register(r'user-permissions', UserPermissionViewSet, basename='user-permissions')
router.register(r'user-settings', UserSettingsViewSet, basename='user-settings')
router.register(r'login-devices', LoginDeviceViewSet, basename='login-devices')
router.register(r'bind-phone', BindPhoneViewSet, basename='bind-phone')

router.register(r'', UserViewSet, basename='users')

urlpatterns = [
    path('', include(router.urls)),
    path('me/', UserProfileView.as_view(), name='user-profile'),
    # VIP支付相关
    path('vip/packages/', get_vip_packages, name='vip-packages'),
    path('vip/orders/', get_vip_orders, name='vip-orders'),
    path('vip/create/', create_vip_order, name='vip-create'),
    path('vip/notify/', alipay_notify, name='vip-notify'),
    path('vip/check/', check_order_status, name='vip-check'),
    path('vip/cancel/', cancel_order, name='vip-cancel'),
    path('vip/dev/mark-paid/', dev_mark_order_paid, name='vip-dev-mark-paid'),
] 