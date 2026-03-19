<template>
  <div class="dashboard-content">
    <PageHeader 
      title="VIP会员" 
      :breadcrumb="[{ label: '个人中心' }, { label: 'VIP会员' }]"
      class="animate-slide-up"
    />

    <div class="vip-container">
      <div class="vip-grid">
        <div class="vip-col">
          <!-- 当前VIP状态 -->
          <div class="status-card animate-slide-up" style="animation-delay: 0.05s">
            <div class="card-header">
              <div class="header-icon vip-icon">
                <el-icon><Medal /></el-icon>
              </div>
              <h3>会员状态</h3>
            </div>
            <div class="status-content" v-if="currentVip">
              <div class="status-badge" :class="currentVip.is_vip_active ? 'active' : ''">
                <el-icon :size="28"><Medal /></el-icon>
              </div>
              <div class="status-info">
                <h4 v-if="currentVip.is_vip_active">
                  VIP会员
                  <span class="vip-tag active">已开通</span>
                </h4>
                <h4 v-else>
                  普通用户
                  <span class="vip-tag">未开通</span>
                </h4>
                <p v-if="currentVip.is_vip_active && currentVip.vip_expire_time">
                  有效期至 {{ formatDate(currentVip.vip_expire_time) }}
                </p>
                <p v-else>开通VIP享受更多特权</p>
              </div>
              <div class="benefits-list" v-if="currentVip.is_vip_active">
                <div class="benefit">
                  <el-icon><Edit /></el-icon>
                  <span>字幕创作工具访问权限</span>
                </div>
              </div>
            </div>
          </div>

          <!-- VIP套餐选择 -->
          <div class="packages-card animate-slide-up" style="animation-delay: 0.1s">
            <div class="card-header">
              <div class="header-icon">
                <el-icon><ShoppingCart /></el-icon>
              </div>
              <div class="header-text">
                <h3>选择套餐</h3>
                <span class="header-sub">开通后立即生效，到期时间自动延长</span>
              </div>
            </div>

            <!-- 时长选择 -->
            <div class="duration-cards">
              <div 
                v-for="(price, key) in currentPackage?.prices" 
                :key="key"
                class="duration-card"
                :class="{ active: selectedDuration === key, recommended: key === 'quarterly' }"
                @click="selectedDuration = key"
              >
                <div class="card-badge" v-if="price.discount">
                  {{ price.discount }}
                </div>
                <div class="card-recommend" v-else-if="key === 'quarterly'">
                  推荐
                </div>
                
                <div class="duration-label">{{ price.label }}</div>
                
                <div class="card-price">
                  <span class="currency">¥</span>
                  <span class="amount">{{ price.price }}</span>
                </div>
                
                <div class="card-original-box">
                  <span class="card-original" v-if="price.original_price > price.price">
                    ¥{{ price.original_price }}
                  </span>
                  <span class="card-months">{{ price.months }}个月</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="vip-col">
          <!-- 支付区域 -->
          <div class="payment-card animate-slide-up" style="animation-delay: 0.15s">
            <div class="card-header">
              <div class="header-icon">
                <el-icon><Wallet /></el-icon>
              </div>
              <h3>确认支付</h3>
            </div>
            <div class="payment-content">
              <div class="payment-summary">
                <div class="summary-item">
                  <span class="label">套餐</span>
                  <span class="value">{{ displayPackageName }}</span>
                </div>
                <div class="summary-item">
                  <span class="label">时长</span>
                  <span class="value">{{ currentDuration?.label }}</span>
                </div>
                <div class="summary-item total">
                  <span class="label">应付金额</span>
                  <span class="value">¥{{ selectedPrice }}</span>
                </div>
              </div>
              <el-button 
                type="primary" 
                class="pay-btn"
                :loading="paying"
                @click="handlePay"
              >
                <el-icon><Wallet /></el-icon>
                <span>立即支付</span>
              </el-button>
            </div>
          </div>

          <!-- 订单记录 -->
          <div class="orders-card animate-slide-up" style="animation-delay: 0.2s">
            <div class="card-header">
              <div class="header-icon">
                <el-icon><Document /></el-icon>
              </div>
              <h3>订单记录</h3>
              <el-button text class="toggle-btn" @click="showAllOrders = !showAllOrders">
                {{ showAllOrders ? '收起' : '查看全部' }}
              </el-button>
            </div>
            
            <div class="orders-list" v-if="orders.length">
              <div 
                v-for="order in displayOrders" 
                :key="order.id" 
                class="order-item"
              >
                <div class="order-left">
                  <div class="order-title">{{ order.vip_level_name }} · {{ order.months }}个月</div>
                  <div class="order-meta">
                    <span>{{ order.order_id }}</span>
                    <span>{{ formatDateTime(order.created_at) }}</span>
                  </div>
                </div>
                <div class="order-right">
                  <div class="order-amount">¥{{ order.amount }}</div>
                  <span class="order-status" :class="order.status">
                    {{ order.status_display }}
                  </span>
                  <el-button
                    v-if="order.status === 'pending'"
                    text
                    class="cancel-order-btn"
                    @click="handleCancelOrder(order.order_id)"
                  >
                    取消订单
                  </el-button>
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无订单记录" :image-size="80" />
          </div>
        </div>
      </div>
    </div>

    <!-- 支付弹窗 -->
    <el-dialog 
      v-model="showPayDialog" 
      title="正在支付" 
      width="420px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <div class="pay-dialog-content">
        <div class="pay-qr-hint" v-if="payUrl">
          <div class="pay-title">支付页面已在新窗口打开</div>
          <div class="pay-subtitle">如未弹出，请点击下方按钮重新打开或复制链接手动打开</div>
          <div class="pay-summary">
            <div class="pay-summary-item">
              <span class="k">套餐</span>
              <span class="v">{{ displayPackageName }}</span>
            </div>
            <div class="pay-summary-item">
              <span class="k">时长</span>
              <span class="v">{{ currentDuration?.label }}</span>
            </div>
            <div class="pay-summary-item total">
              <span class="k">应付</span>
              <span class="v">¥{{ selectedPrice }}</span>
            </div>
          </div>
          <div class="pay-order" v-if="currentOrderId">
            订单号：<span class="order-id">{{ currentOrderId }}</span>
          </div>
        </div>
        <div class="pay-actions">
          <div class="pay-actions-primary">
            <el-button type="primary" class="pay-action-main" @click="checkPayment" :loading="checking">
              我已完成支付
            </el-button>
          </div>

          <div class="pay-actions-secondary">
            <el-button @click="openPayUrl" v-if="payUrl">
              重新打开支付页面
            </el-button>
            <el-button @click="copyPayUrl" v-if="payUrl">
              复制支付链接
            </el-button>
            <el-button
              v-if="isDev"
              type="success"
              @click="handleMockPaid"
              :loading="mocking"
              :disabled="mocking"
            >
              模拟支付成功（开发）
            </el-button>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Medal, Edit, Wallet, ShoppingCart, Document } from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import { 
  getVipPackages, 
  getVipOrders, 
  createVipOrder, 
  checkOrderStatus,
  cancelVipOrder,
  devMarkVipOrderPaid
} from '@/api/user'

// 数据
const packages = ref([])
const currentVip = ref(null)
const orders = ref([])
const selectedDuration = ref('monthly')
const paying = ref(false)
const checking = ref(false)
const mocking = ref(false)
const showAllOrders = ref(false)
const showPayDialog = ref(false)
const payUrl = ref('')
const currentOrderId = ref('')
let checkTimer = null

const isDev = import.meta.env.DEV

// 计算属性
const currentPackage = computed(() => {
  return packages.value?.[0]
})

const currentDuration = computed(() => {
  return currentPackage.value?.prices[selectedDuration.value]
})

const selectedPrice = computed(() => {
  return currentDuration.value?.price || '0.00'
})

const displayPackageName = computed(() => {
  const rawName = currentPackage.value?.name
  if (!rawName) return 'VIP会员'

  // 后端可能返回“青铜VIP/白银VIP/黄金VIP”等，这里统一对外展示为“VIP会员”
  const normalized = String(rawName).replace(/\s+/g, '')
  if (normalized.includes('VIP') && (normalized.includes('青铜') || normalized.includes('白银') || normalized.includes('黄金') || normalized.includes('钻石'))) {
    return 'VIP会员'
  }
  return rawName
})

const displayOrders = computed(() => {
  if (showAllOrders.value) {
    return orders.value
  }
  return orders.value.slice(0, 5)
})

// 方法
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const getOrderStatusType = (status) => {
  const types = {
    pending: 'warning',
    paid: 'success',
    cancelled: 'info',
    refunded: 'danger'
  }
  return types[status] || 'info'
}

// 获取VIP套餐
const fetchPackages = async () => {
  try {
    const res = await getVipPackages()
    packages.value = res.packages || []
    currentVip.value = res.current_vip || null
  } catch (error) {
    console.error('获取VIP套餐失败:', error)
    ElMessage.error('获取VIP套餐失败')
  }
}

// 获取订单列表
const fetchOrders = async () => {
  try {
    const res = await getVipOrders()
    orders.value = res.orders || []
  } catch (error) {
    console.error('获取订单列表失败:', error)
  }
}

// 发起支付
const handlePay = async () => {
  if (!selectedDuration.value) {
    ElMessage.error('请选择购买时长')
    return
  }

  if (!currentPackage.value) {
    ElMessage.error('套餐信息加载中，请稍后再试')
    return
  }

  paying.value = true
  try {
    const res = await createVipOrder({
      duration: selectedDuration.value,
      payment_method: 'alipay'
    })
    
    if (res.pay_url) {
      currentOrderId.value = res.order_id
      payUrl.value = res.pay_url
      showPayDialog.value = true
      
      // 打开支付页面
      openPayUrl()
      
      // 开始轮询检查支付状态
      startCheckPayment()
    }
  } catch (error) {
    console.error('创建订单失败:', error)
    const backendError = error?.response?.data?.error
    ElMessage.error(backendError || '创建订单失败')
  } finally {
    paying.value = false
  }
}

// 打开支付页面
const openPayUrl = () => {
  if (payUrl.value) {
    const w = window.open(payUrl.value, '_blank')
    if (!w) {
      ElMessage.warning('浏览器可能拦截了弹窗，请允许本站点弹窗或点击“复制支付链接”手动打开')
    }
  }
}

const copyPayUrl = async () => {
  if (!payUrl.value) return
  try {
    await navigator.clipboard.writeText(payUrl.value)
    ElMessage.success('支付链接已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制链接')
  }
}

const handleCancelOrder = async (orderId) => {
  if (!orderId) return
  try {
    await cancelVipOrder(orderId)
    ElMessage.success('订单已取消')

    if (currentOrderId.value === orderId) {
      if (checkTimer) {
        clearInterval(checkTimer)
        checkTimer = null
      }
      showPayDialog.value = false
      payUrl.value = ''
      currentOrderId.value = ''
    }

    fetchOrders()
  } catch (error) {
    const backendError = error?.response?.data?.error
    ElMessage.error(backendError || '取消订单失败')
  }
}

const handleMockPaid = async () => {
  if (!currentOrderId.value) {
    ElMessage.error('缺少订单号')
    return
  }

  mocking.value = true
  try {
    await devMarkVipOrderPaid(currentOrderId.value)
    ElMessage.success('已模拟支付成功')

    if (checkTimer) {
      clearInterval(checkTimer)
      checkTimer = null
    }

    showPayDialog.value = false
    payUrl.value = ''
    currentOrderId.value = ''

    await fetchPackages()
    await fetchOrders()
  } catch (error) {
    const backendError = error?.response?.data?.error
    ElMessage.error(backendError || '模拟支付失败')
  } finally {
    mocking.value = false
  }
}

// 开始检查支付状态
const startCheckPayment = () => {
  checkTimer = setInterval(() => {
    checkPayment()
  }, 3000) // 每3秒检查一次
}

// 检查支付状态
const checkPayment = async () => {
  if (!currentOrderId.value) return
  
  checking.value = true
  try {
    const res = await checkOrderStatus({ order_id: currentOrderId.value })
    
    if (res.status === 'paid') {
      // 支付成功
      clearInterval(checkTimer)
      checkTimer = null
      showPayDialog.value = false
      
      ElMessage.success('支付成功！VIP已开通')
      
      // 刷新数据
      fetchPackages()
      fetchOrders()
    }
  } catch (error) {
    console.error('检查支付状态失败:', error)
  } finally {
    checking.value = false
  }
}

// 生命周期
onMounted(() => {
  fetchPackages()
  fetchOrders()
})

onUnmounted(() => {
  if (checkTimer) {
    clearInterval(checkTimer)
  }
})
</script>

<style scoped>
 .dashboard-content {
  padding: 16px;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
 }
 
/* 容器 */
.vip-container {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.vip-grid {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 14px;
  align-items: start;
}

.vip-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

 /* 动画定义 */
 @keyframes subtleSlideUp {
   from {
     opacity: 0;
     transform: translateY(10px);
   }
   to {
     opacity: 1;
     transform: translateY(0);
   }
 }
 
 .animate-slide-up {
   animation: subtleSlideUp 0.4s ease-out both;
 }

/* 通用卡片样式 */
.status-card,
.packages-card,
.payment-card,
.orders-card {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid #f3f4f6;
}

.card-header .header-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
}

.card-header .header-icon.vip-icon {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  color: #d97706;
}

.card-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  margin: 0;
}

.card-header .toggle-btn {
  margin-left: auto;
  font-size: 13px;
  color: #6b7280;
}

/* 状态卡片 */
.status-content {
  padding: 16px 18px;
  display: flex;
  align-items: center;
  gap: 20px;
}

.status-badge {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
}

.status-badge.active {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  color: #d97706;
}

.status-info h4 {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  margin: 0 0 4px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.vip-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #f3f4f6;
  color: #6b7280;
  font-weight: 500;
}

.vip-tag.active {
  background: #d1fae5;
  color: #059669;
}

.status-info p {
  font-size: 13px;
  color: #6b7280;
  margin: 0;
}

.benefits-list {
  margin-left: auto;
  display: flex;
  gap: 16px;
}

.benefit {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #6b7280;
}

/* 套餐卡片 */
.packages-card {
  padding-bottom: 24px;
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.header-sub {
  font-size: 12px;
  color: #9ca3af;
  font-weight: normal;
}

/* 时长卡片 */
.duration-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  padding: 24px 20px 0;
}

.duration-card {
  padding: 24px 16px;
  border-radius: 12px;
  border: 2px solid #f3f4f6;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.duration-card:hover {
  border-color: #fbbf24;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.duration-card.active {
  border-color: #d97706;
  background: #fffcf0;
  box-shadow: 0 4px 20px rgba(217, 119, 6, 0.1);
}

.card-badge, .card-recommend {
  position: absolute;
  top: -2px;
  right: -2px;
  padding: 4px 10px;
  border-radius: 0 10px 0 10px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
}

.card-badge {
  background: linear-gradient(135deg, #ff4d4f 0%, #ff7875 100%);
}

.card-recommend {
  background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
}

.duration-label {
  font-size: 15px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 12px;
}

.card-price {
  margin-bottom: 8px;
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.card-price .currency {
  font-size: 16px;
  font-weight: 600;
  color: #d97706;
}

.card-price .amount {
  font-size: 32px;
  font-weight: 700;
  color: #d97706;
  line-height: 1;
}

.card-original-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 40px;
  justify-content: center;
}

.card-original {
  font-size: 13px;
  color: #9ca3af;
  text-decoration: line-through;
}

.card-months {
  font-size: 13px;
  color: #6b7280;
}

/* 支付卡片 */
.payment-card {
  overflow: hidden;
}

.payment-content {
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.payment-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #f9fafb;
  padding: 16px;
  border-radius: 10px;
}

.summary-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.summary-item .label {
  font-size: 14px;
  color: #6b7280;
}

.summary-item .value {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.summary-item.total {
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px dashed #e5e7eb;
}

.summary-item.total .label {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
}

.summary-item.total .value {
  font-size: 24px;
  font-weight: 700;
  color: #d97706;
}

.pay-btn {
  height: 48px;
  width: 100%;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
  border: none;
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(217, 119, 6, 0.2);
  transition: all 0.3s;
}

.pay-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(217, 119, 6, 0.3);
  opacity: 0.9;
}

/* 订单卡片 */
.orders-list {
  padding: 0 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.order-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #f3f4f6;
}

.order-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.order-title {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.order-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #9ca3af;
}

.order-right {
  text-align: right;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-end;
}

.order-amount {
  font-size: 15px;
  font-weight: 600;
  color: #374151;
}

.order-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.order-status.paid {
  background: #d1fae5;
  color: #059669;
}

.order-status.pending {
  background: #fef3c7;
  color: #d97706;
}

.order-status.cancelled {
  background: #f3f4f6;
  color: #6b7280;
}

.order-status.refunded {
  background: #fee2e2;
  color: #dc2626;
}

.cancel-order-btn {
  margin-top: 2px;
  font-size: 12px;
  color: #6b7280;
}

.cancel-order-btn:hover {
  color: #111827;
}

/* 支付弹窗 */
.pay-dialog-content {
  padding: 18px 18px 14px;
}

.pay-qr-hint {
  margin-bottom: 14px;
}

.pay-title {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  text-align: center;
}

.pay-subtitle {
  margin-top: 6px;
  font-size: 13px;
  color: #6b7280;
  text-align: center;
}

.pay-summary {
  margin-top: 14px;
  background: #fafafa;
  border: 1px solid #f3f4f6;
  border-radius: 10px;
  padding: 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 12px;
}

.pay-summary-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
}

.pay-summary-item .k {
  color: #6b7280;
}

.pay-summary-item .v {
  color: #111827;
  font-weight: 500;
}

.pay-summary-item.total {
  grid-column: 1 / -1;
}

.pay-summary-item.total .v {
  color: #d97706;
  font-weight: 700;
}

.pay-order {
  margin-top: 10px;
  text-align: center;
  font-size: 12px;
  color: #6b7280;
}

.order-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  color: #111827;
}

.pay-qr-hint p {
  margin: 6px 0;
  font-size: 14px;
  color: #374151;
}

.hint-text {
  font-size: 13px;
  color: #6b7280;
}

.pay-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pay-actions-primary {
  display: flex;
  justify-content: center;
}

.pay-action-main {
  min-width: 160px;
}

.pay-actions-secondary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

/* 响应式 */
@media (max-width: 1024px) {
  .vip-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .dashboard-content {
    padding: 12px;
  }
 
  .duration-cards {
    grid-template-columns: 1fr;
    padding: 16px 12px 0;
  }
  
  .duration-card {
    padding: 16px;
  }

  .benefits-list {
    display: none;
  }
  
  .status-content {
    flex-direction: column;
    text-align: center;
    gap: 12px;
  }
}
</style>
