import axios from 'axios';
import { getToken, getRefreshToken, setToken, removeToken } from '@/utils/auth';

// Create axios instance
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 15000
});

// Request interceptor
service.interceptors.request.use(
  config => {
    const token = getToken();
    
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Response interceptor
service.interceptors.response.use(
  response => {
    return response.data;
  },
  async error => {
    
    // 如果是401错误且没有重试过，尝试刷新token
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      
      try {
        const refreshToken = getRefreshToken();
        
        if (!refreshToken) {
          // 如果没有刷新令牌，跳转到登录页
          handleAuthError();
          return Promise.reject(error);
        }
        
        // 调用刷新令牌API
        const response = await axios.post(
          `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'}/token/refresh/`,
          { refresh: refreshToken }
        );
        
        const { access } = response.data;
        
        // 更新访问令牌
        setToken(access);
        
        // 使用新令牌重新发送原始请求
        error.config.headers['Authorization'] = `Bearer ${access}`;
        return axios(error.config);
      } catch (refreshError) {
        // 刷新失败，跳转到登录页
        handleAuthError();
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

// 处理认证错误，跳转到登录页
function handleAuthError() {
  removeToken();
  // 避免重复跳转
  if (window.location.pathname !== '/auth' && window.location.pathname !== '/login') {
    window.location.href = '/auth?expired=1';
  }
}

// User login
export function login(data) {
  return service({
    url: '/auth/login/',
    method: 'post',
    data
  });
}

// User logout - 传递 refresh token 以加入黑名单
export function logout() {
  const refreshToken = getRefreshToken();
  return service({
    url: '/auth/logout/',
    method: 'post',
    data: { refresh: refreshToken }
  });
}

// Get user info
export function getUserInfo() {
  return service({
    url: '/users/me/',
    method: 'get'
  })
  .then(response => {
    if (!response || !response.id) {
      return Promise.reject(new Error('无效的用户信息响应'));
    }
    return response;
  })
  .catch(error => {
    console.error('获取用户信息失败:', error);
    return Promise.reject(error);
  });
}

// Get user info by ID
export function getUserById(userId) {
  return service({
    url: `/users/${userId}/`,
    method: 'get'
  })
  .then(response => {
    if (!response || !response.id) {
      return Promise.reject(new Error('无效的用户信息响应'));
    }
    return response;
  })
  .catch(error => {
    console.error('获取用户信息失败:', error);
    return Promise.reject(error);
  });
}

// Register user
export function register(data) {
  return service({
    url: '/auth/register/',
    method: 'post',
    data
  });
}

// Update user profile
export function updateUserProfile(data) {
  return service({
    url: '/users/update-profile/',
    method: 'put',
    data
  });
}

// Upload avatar
export function uploadAvatar(file) {
  const formData = new FormData();
  formData.append('avatar', file);
  
  return service({
    url: '/users/upload-avatar/',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  .then(response => {
    return response;
  })
  .catch(error => {
    console.error('Avatar upload error:', error);
    return Promise.reject(error);
  });
}

// Send verification code
export function sendVerificationCode(data) {
  return service({
    url: '/users/send-verification-code/',
    method: 'post',
    data
  });
}

// Verify email
export function verifyEmail(code) {
  return service({
    url: '/users/verify-email/',
    method: 'post',
    data: { code }
  });
}

// Change password with verification code
export function changePasswordWithCode(data) {
  return service({
    url: '/users/change-password-with-code/',
    method: 'post',
    data
  });
}

// Change email with verification code
export function changeEmailWithCode(data) {
  return service({
    url: '/users/change-email-with-code/',
    method: 'post',
    data
  });
}

// Change password (old way)
export function changePassword(data) {
  return service({
    url: '/users/change-password/',
    method: 'put',
    data
  });
}

/**
 * 获取图片验证码
 * @returns {Promise} { hashkey, image_url }
 */
export function getCaptcha() {
  return service({
    url: '/auth/captcha/',
    method: 'get'
  });
}

// Send test email
export function sendTestEmail(email) {
  return service({
    url: '/users/test-email/',
    method: 'post',
    data: { email }
  });
}

// Get dashboard statistics
export function getDashboardStats() {
  return service({
    url: '/users/dashboard/stats/',
    method: 'get'
  });
}

// Get dashboard chart data
export function getDashboardChartData(days = 7) {
  return service({
    url: '/users/dashboard/chart-data/',
    method: 'get',
    params: { days }
  });
}

// 添加消息通知相关的API调用函数

/**
 * 获取消息通知列表
 * @param {Object} params 查询参数，包括type（消息类型，可选值：all, system, interaction, private）
 * @returns {Promise} 消息列表
 */
export function getNotifications(params) {
  return service({
    url: '/users/notifications/',
    method: 'get',
    params
  }).then(response => {
    // 确保返回的是数组
    return response?.results || response || [];
  }).catch(error => {
    console.error('获取消息通知失败:', error);
    return []; // 错误时返回空数组
  });
}

/**
 * 标记单个消息为已读
 * @param {Number} id 消息ID
 * @returns {Promise}
 */
export function markNotificationAsRead(id) {
  return service({
    url: `/users/notifications/${id}/mark_read/`,
    method: 'post'
  });
}

/**
 * 标记所有消息为已读
 * @returns {Promise}
 */
export function markAllNotificationsAsRead() {
  return service({
    url: '/users/notifications/mark_all_read/',
    method: 'post'
  });
}

/**
 * 删除单个消息
 * @param {Number} id 消息ID
 * @returns {Promise}
 */
export function deleteNotification(id) {
  return service({
    url: `/users/notifications/${id}/`,
    method: 'delete'
  });
}

/**
 * 清空所有消息
 * @returns {Promise}
 */
export function clearAllNotifications() {
  return service({
    url: '/users/notifications/clear_all/',
    method: 'delete'
  });
}

/**
 * 获取未读消息数量
 * @returns {Promise}
 */
export function getUnreadNotificationCount() {
  return service({
    url: '/users/notifications/unread_count/',
    method: 'get'
  });
}

/**
 * 获取通知设置
 * @returns {Promise}
 */
export function getNotificationSettings() {
  return service({
    url: '/users/notification-settings/',
    method: 'get'
  });
}

/**
 * 更新通知设置
 * @param {Object} data 通知设置数据
 * @returns {Promise}
 */
export function updateNotificationSettings(data) {
  return service({
    url: '/users/notification-settings/',
    method: 'put',
    data
  });
}

/**
 * 获取用户综合设置
 * @returns {Promise}
 */
export function getUserSettings() {
  return service({
    url: '/users/user-settings/',
    method: 'get'
  });
}

/**
 * 更新用户综合设置
 * @param {Object} data 设置数据
 * @returns {Promise}
 */
export function updateUserSettings(data) {
  return service({
    url: '/users/user-settings/',
    method: 'put',
    data
  });
}

/**
 * 获取隐私设置
 * @returns {Promise}
 */
export function getPrivacySettings() {
  return service({
    url: '/users/user-settings/privacy/',
    method: 'get'
  });
}

/**
 * 更新隐私设置
 * @param {Object} data 隐私设置数据
 * @returns {Promise}
 */
export function updatePrivacySettings(data) {
  return service({
    url: '/users/user-settings/update_privacy/',
    method: 'put',
    data
  });
}

/**
 * 获取播放设置
 * @returns {Promise}
 */
export function getPlaybackSettings() {
  return service({
    url: '/users/user-settings/playback/',
    method: 'get'
  });
}

/**
 * 更新播放设置
 * @param {Object} data 播放设置数据
 * @returns {Promise}
 */
export function updatePlaybackSettings(data) {
  return service({
    url: '/users/user-settings/update_playback/',
    method: 'put',
    data
  });
}

/**
 * 获取界面设置
 * @returns {Promise}
 */
export function getInterfaceSettings() {
  return service({
    url: '/users/user-settings/interface/',
    method: 'get'
  });
}

/**
 * 更新界面设置
 * @param {Object} data 界面设置数据
 * @returns {Promise}
 */
export function updateInterfaceSettings(data) {
  return service({
    url: '/users/user-settings/update_interface/',
    method: 'put',
    data
  });
}

/**
 * 获取登录设备列表
 * @returns {Promise}
 */
export function getLoginDevices() {
  return service({
    url: '/users/login-devices/',
    method: 'get'
  });
}

/**
 * 移除登录设备
 * @param {Number} deviceId 设备ID
 * @returns {Promise}
 */
export function removeLoginDevice(deviceId) {
  return service({
    url: `/users/login-devices/${deviceId}/`,
    method: 'delete'
  });
}

/**
 * 移除所有其他设备
 * @returns {Promise}
 */
export function removeAllOtherDevices() {
  return service({
    url: '/users/login-devices/remove_all/',
    method: 'post'
  });
}

/**
 * 发送手机验证码
 * @param {String} phone 手机号
 * @returns {Promise}
 */
export function sendPhoneVerificationCode(phone) {
  return service({
    url: '/users/bind-phone/send_code/',
    method: 'post',
    data: { phone }
  });
}

/**
 * 绑定手机号
 * @param {String} phone 手机号
 * @param {String} code 验证码
 * @returns {Promise}
 */
export function bindPhone(phone, code) {
  return service({
    url: '/users/bind-phone/bind/',
    method: 'post',
    data: { phone, code }
  });
}

/**
 * 解绑手机号
 * @returns {Promise}
 */
export function unbindPhone() {
  return service({
    url: '/users/bind-phone/unbind/',
    method: 'post'
  });
}

// Subscribe to user
export function subscribeUser(userId) {
  return service({
    url: `/users/${userId}/subscribe/`,
    method: 'post'
  })
  .then(response => {
    return response;
  })
  .catch(error => {
    console.error('订阅用户失败:', error);
    return Promise.reject(error);
  });
}

// Unsubscribe from user
export function unsubscribeUser(userId) {
  return service({
    url: `/users/${userId}/unsubscribe/`,
    method: 'post'
  })
  .then(response => {
    return response;
  })
  .catch(error => {
    console.error('取消订阅用户失败:', error);
    return Promise.reject(error);
  });
}

// Get user's videos
export function getUserVideos(userId, params = {}) {
  return service({
    url: `/videos/videos/`,
    method: 'get',
    params: {
      user: userId,
      is_published: true,
      status: 'approved',
      ...params
    }
  })
  .then(response => {
    return response;
  })
  .catch(error => {
    console.error('获取用户视频失败:', error);
    return Promise.reject(error);
  });
}

// Check subscription status
export function checkSubscriptionStatus(userId) {
  return service({
    url: `/users/${userId}/subscription_status/`,
    method: 'get'
  })
  .then(response => {
    return response;
  })
  .catch(error => {
    console.error('检查订阅状态失败:', error);
    return Promise.reject(error);
  });
}

// ==================== VIP支付相关 ====================

/**
 * 获取VIP套餐列表
 * @returns {Promise}
 */
export function getVipPackages() {
  return service({
    url: '/users/vip/packages/',
    method: 'get'
  });
}

/**
 * 获取VIP订单列表
 * @returns {Promise}
 */
export function getVipOrders() {
  return service({
    url: '/users/vip/orders/',
    method: 'get'
  });
}

/**
 * 创建VIP订单
 * @param {Object} data { vip_level, duration, payment_method }
 * @returns {Promise}
 */
export function createVipOrder(data) {
  return service({
    url: '/users/vip/create/',
    method: 'post',
    data
  });
}

/**
 * 检查订单状态
 * @param {Object} params { order_id }
 * @returns {Promise}
 */
export function checkOrderStatus(params) {
  return service({
    url: '/users/vip/check/',
    method: 'get',
    params
  });
}

/**
 * 取消订单
 * @param {String} orderId 订单号
 * @returns {Promise}
 */
export function cancelVipOrder(orderId) {
  return service({
    url: '/users/vip/cancel/',
    method: 'post',
    data: { order_id: orderId }
  });
}

/**
 * 开发环境：模拟VIP订单支付成功
 * @param {String} orderId 订单号
 * @returns {Promise}
 */
export function devMarkVipOrderPaid(orderId) {
  return service({
    url: '/users/vip/dev/mark-paid/',
    method: 'post',
    data: { order_id: orderId }
  });
}

export default service; 