<template>
  <div class="user-management-container animate__animated animate__fadeIn animate__faster">
    <PageHeader
      title="用户管理"
      :breadcrumb="[{ label: '管理后台' }, { label: '用户管理' }]"
      class="animate__animated animate__fadeInDown animate__faster"
    />

    <!-- 统计卡片 -->
    <div class="stats-section animate__animated animate__fadeInUp animate__fast">
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="stat-card animate__animated animate__zoomIn animate__faster">
            <div class="stat-icon" style="background: #667eea;">
              <el-icon><User /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ stats.total_users }}</div>
              <div class="stat-label">总用户数</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card animate__animated animate__zoomIn animate__faster">
            <div class="stat-icon" style="background: #f093fb;">
              <el-icon><Star /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ stats.vip_users }}</div>
              <div class="stat-label">VIP用户</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card animate__animated animate__zoomIn animate__faster">
            <div class="stat-icon" style="background: #4facfe;">
              <el-icon><CircleCheck /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ stats.active_users }}</div>
              <div class="stat-label">活跃用户</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card animate__animated animate__zoomIn animate__faster">
            <div class="stat-icon" style="background: #fa709a;">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ stats.new_users_today }}</div>
              <div class="stat-label">今日新增</div>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 搜索和筛选区域 -->
    <div class="filter-section animate__animated animate__fadeInUp animate__fast">
      <el-row :gutter="20">
        <el-col :span="8">
          <el-input
            v-model="searchQuery"
            placeholder="搜索用户名、昵称或邮箱"
            clearable
            @input="handleSearch"
            size="large"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="4">
          <el-select v-model="roleFilter" placeholder="角色筛选" clearable @change="handleFilter" size="large">
            <el-option label="普通用户" value="user" />
            <el-option label="VIP用户" value="vip" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="vipStatusFilter" placeholder="VIP状态" clearable @change="handleFilter" size="large">
            <el-option label="活跃VIP" value="active" />
            <el-option label="过期VIP" value="expired" />
            <el-option label="非VIP" value="none" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="statusFilter" placeholder="账号状态" clearable @change="handleFilter" size="large">
            <el-option label="正常" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="loadUsers" size="large" style="width: 100%;">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </el-col>
      </el-row>
    </div>

    <!-- 用户列表 -->
    <div class="table-section animate__animated animate__fadeInUp animate__fast">
      <el-table
        :data="userList"
        style="width: 100%"
        v-loading="loading"
        element-loading-text="加载中..."
        :row-class-name="tableRowClassName"
        :scrollbar-always-on="false"
      >
        <el-table-column prop="avatar" label="用户信息" width="280">
          <template #default="scope">
            <div class="user-info-cell">
              <el-avatar :size="50" :src="scope.row.avatar" class="user-avatar">
                {{ scope.row.username.charAt(0).toUpperCase() }}
              </el-avatar>
              <div class="user-details">
                <div class="user-name">
                  {{ scope.row.username }}
                  <el-tag v-if="scope.row.is_vip" size="small" type="warning" effect="dark">VIP</el-tag>
                </div>
                <div class="user-nickname">{{ scope.row.last_name || '未设置昵称' }}</div>
                <div class="user-email">{{ scope.row.email }}</div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="role_display" label="角色" width="100" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.role === 'vip' ? 'success' : 'info'" effect="dark">
              {{ scope.row.role_display }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="vip_info" label="VIP信息" width="200">
          <template #default="scope">
            <div v-if="scope.row.is_vip" class="vip-info-cell">
              <el-tag
                :type="getVipTagType(scope.row.vip_status)"
                effect="dark"
                size="small"
              >
                {{ scope.row.vip_level_display }}
              </el-tag>
              <div class="vip-expire">
                到期: {{ formatDate(scope.row.vip_expire_time, 'date') }}
              </div>
              <div class="vip-days" :class="getVipDaysClass(scope.row.vip_expire_time)">
                剩余 {{ getRemainingDays(scope.row.vip_expire_time) }} 天
              </div>
            </div>
            <span v-else class="text-muted">未开通VIP</span>
          </template>
        </el-table-column>

        <el-table-column prop="stats" label="用户数据" width="180">
          <template #default="scope">
            <div class="user-stats-cell">
              <div class="stat-item">
                <el-icon><VideoPlay /></el-icon>
                <span>视频: {{ scope.row.video_count || 0 }}</span>
              </div>
              <div class="stat-item">
                <el-icon><View /></el-icon>
                <span>观看: {{ scope.row.view_count || 0 }}</span>
              </div>
              <div class="stat-item">
                <el-icon><ChatDotRound /></el-icon>
                <span>评论: {{ scope.row.comment_count || 0 }}</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="is_active" label="状态" width="80" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'danger'" effect="dark">
              {{ scope.row.is_active ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="注册时间" width="160">
          <template #default="scope">
            <div class="time-cell">
              <div>{{ formatDate(scope.row.created_at, 'date') }}</div>
              <div class="time-sub">{{ formatDate(scope.row.created_at, 'time') }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="280" fixed="right">
          <template #default="scope">
            <el-button
              size="small"
              type="primary"
              @click="viewUserDetail(scope.row)"
              :icon="View"
            >
              详情
            </el-button>
            <el-button
              v-if="!scope.row.is_vip"
              size="small"
              type="success"
              @click="openVipDialog(scope.row)"
              :icon="Star"
            >
              设置VIP
            </el-button>
            <el-button
              v-else
              size="small"
              type="warning"
              @click="cancelVip(scope.row)"
              :icon="Close"
            >
              取消VIP
            </el-button>
            <el-button
              size="small"
              :type="scope.row.is_active ? 'danger' : 'success'"
              @click="toggleUserActive(scope.row)"
              :icon="scope.row.is_active ? Lock : Unlock"
            >
              {{ scope.row.is_active ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <div class="pagination-section" v-if="total > 0">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
        background
      />
    </div>

    <!-- 设置VIP对话框 -->
    <el-dialog
      v-model="vipDialogVisible"
      title="设置VIP"
      width="500px"
      :close-on-click-modal="false"
      class="animate__animated animate__zoomIn animate__faster"
      append-to-body
    >
      <el-form :model="vipForm" label-width="100px" class="animate__animated animate__fadeIn">
        <el-form-item label="用户信息">
          <div class="dialog-user-info">
            <el-avatar :size="40" :src="selectedUser?.avatar">
              {{ selectedUser?.username?.charAt(0).toUpperCase() }}
            </el-avatar>
            <div>
              <div>{{ selectedUser?.username }}</div>
              <div class="text-muted">{{ selectedUser?.email }}</div>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="VIP等级">
          <el-select v-model="vipForm.vip_level" placeholder="选择VIP等级" style="width: 100%;">
            <el-option label="🥉 青铜VIP" :value="1" />
            <el-option label="🥈 白银VIP" :value="2" />
            <el-option label="🥇 黄金VIP" :value="3" />
          </el-select>
        </el-form-item>
        <el-form-item label="购买月数">
          <el-input-number
            v-model="vipForm.months"
            :min="1"
            :max="12"
            :precision="0"
            style="width: 100%;"
          />
          <div class="form-tip">到期时间: {{ calculateExpireDate() }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="vipDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmSetVip">确定</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 用户详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="用户详情"
      width="900px"
      :close-on-click-modal="false"
      top="5vh"
      class="animate__animated animate__zoomIn animate__faster"
      append-to-body
    >
      <div v-if="selectedUser" class="user-detail-content animate__animated animate__fadeIn">
        <el-row :gutter="24">
          <el-col :span="7">
            <div class="detail-avatar-section">
              <el-avatar :size="100" :src="selectedUser.avatar">
                {{ selectedUser.username.charAt(0).toUpperCase() }}
              </el-avatar>
              <div class="detail-username">{{ selectedUser.username }}</div>
              <el-tag v-if="selectedUser.is_vip" type="warning" effect="dark" size="large">VIP用户</el-tag>
              <el-tag v-else type="info" size="large">普通用户</el-tag>
            </div>
            
            <el-divider />
            
            <div class="detail-stats-section">
              <div class="detail-stat-item">
                <el-icon class="stat-icon"><VideoPlay /></el-icon>
                <div class="stat-info">
                  <div class="stat-value">{{ selectedUser.video_count || 0 }}</div>
                  <div class="stat-label">上传视频</div>
                </div>
              </div>
              <div class="detail-stat-item">
                <el-icon class="stat-icon"><View /></el-icon>
                <div class="stat-info">
                  <div class="stat-value">{{ selectedUser.view_count || 0 }}</div>
                  <div class="stat-label">总观看数</div>
                </div>
              </div>
              <div class="detail-stat-item">
                <el-icon class="stat-icon"><ChatDotRound /></el-icon>
                <div class="stat-info">
                  <div class="stat-value">{{ selectedUser.comment_count || 0 }}</div>
                  <div class="stat-label">评论数</div>
                </div>
              </div>
            </div>
          </el-col>
          
          <el-col :span="17">
            <el-descriptions title="基本信息" :column="2" border size="default">
              <el-descriptions-item label="用户ID" label-align="right">{{ selectedUser.id }}</el-descriptions-item>
              <el-descriptions-item label="用户名" label-align="right">{{ selectedUser.username }}</el-descriptions-item>
              <el-descriptions-item label="昵称" label-align="right">{{ selectedUser.last_name || '未设置' }}</el-descriptions-item>
              <el-descriptions-item label="邮箱" label-align="right">{{ selectedUser.email }}</el-descriptions-item>
              <el-descriptions-item label="性别" label-align="right">{{ getGenderText(selectedUser.gender) }}</el-descriptions-item>
              <el-descriptions-item label="生日" label-align="right">{{ selectedUser.birthday || '未设置' }}</el-descriptions-item>
              <el-descriptions-item label="角色" label-align="right">
                <el-tag :type="selectedUser.role === 'vip' ? 'success' : 'info'" effect="dark">
                  {{ selectedUser.role_display }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="账号状态" label-align="right">
                <el-tag :type="selectedUser.is_active ? 'success' : 'danger'" effect="dark">
                  {{ selectedUser.is_active ? '正常' : '禁用' }}
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>

            <el-descriptions 
              v-if="selectedUser.is_vip" 
              title="VIP信息" 
              :column="2" 
              border 
              size="default"
              style="margin-top: 20px;"
            >
              <el-descriptions-item label="VIP等级" label-align="right">
                <el-tag :type="getVipTagType(selectedUser.vip_status)" effect="dark">
                  {{ selectedUser.vip_level_display }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="VIP状态" label-align="right">
                <el-tag :type="getVipTagType(selectedUser.vip_status)" effect="plain">
                  {{ selectedUser.vip_status === 'active' ? '正常' : '已过期' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="到期时间" label-align="right" :span="2">
                {{ formatDate(selectedUser.vip_expire_time) }}
                <span :class="['vip-days-badge', getVipDaysClass(selectedUser.vip_expire_time)]">
                  剩余 {{ getRemainingDays(selectedUser.vip_expire_time) }} 天
                </span>
              </el-descriptions-item>
            </el-descriptions>

            <el-descriptions 
              title="时间信息" 
              :column="1" 
              border 
              size="default"
              style="margin-top: 20px;"
            >
              <el-descriptions-item label="注册时间" label-align="right">
                {{ formatDate(selectedUser.created_at) }}
              </el-descriptions-item>
              <el-descriptions-item label="最后登录" label-align="right">
                {{ formatDate(selectedUser.last_login) }}
              </el-descriptions-item>
            </el-descriptions>
          </el-col>
        </el-row>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="detailDialogVisible = false" size="large">关闭</el-button>
          <el-button 
            v-if="!selectedUser?.is_vip" 
            type="success" 
            @click="openVipDialog(selectedUser); detailDialogVisible = false"
            size="large"
          >
            设置VIP
          </el-button>
          <el-button 
            v-else 
            type="warning" 
            @click="cancelVip(selectedUser); detailDialogVisible = false"
            size="large"
          >
            取消VIP
          </el-button>
          <el-button 
            :type="selectedUser?.is_active ? 'danger' : 'success'" 
            @click="toggleUserActive(selectedUser); detailDialogVisible = false"
            size="large"
          >
            {{ selectedUser?.is_active ? '禁用账号' : '启用账号' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Search, Refresh, User, Star, CircleCheck, TrendCharts,
  VideoPlay, View, ChatDotRound, Lock, Unlock, Close
} from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import request from '@/api/user'

// 响应式数据
const loading = ref(false)
const userList = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const searchQuery = ref('')
const roleFilter = ref('')
const vipStatusFilter = ref('')
const statusFilter = ref('')
const vipDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const selectedUser = ref(null)
const vipForm = ref({
  vip_level: 1,
  months: 1
})

// 统计数据
const stats = ref({
  total_users: 0,
  vip_users: 0,
  active_users: 0,
  new_users_today: 0
})

// 加载统计数据
const loadStats = async () => {
  try {
    const response = await request.get('/users/admin-users/stats/')
    stats.value = response
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

// 加载用户列表
const loadUsers = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }

    if (searchQuery.value) {
      params.search = searchQuery.value
    }

    if (roleFilter.value) {
      params.role = roleFilter.value
    }

    if (vipStatusFilter.value) {
      params.vip_status = vipStatusFilter.value
    }

    if (statusFilter.value) {
      params.status = statusFilter.value
    }

    const response = await request.get('/users/admin-users/', { params })
    userList.value = response.results || []
    total.value = response.total || 0
    
    // 同时刷新统计数据
    loadStats()
  } catch (error) {
    console.error('加载用户列表失败:', error)
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索处理
const handleSearch = () => {
  currentPage.value = 1
  loadUsers()
}

// 筛选处理
const handleFilter = () => {
  currentPage.value = 1
  loadUsers()
}

// 分页大小改变
const handleSizeChange = (newSize) => {
  pageSize.value = newSize
  currentPage.value = 1
  loadUsers()
}

// 页码改变
const handleCurrentChange = (newPage) => {
  currentPage.value = newPage
  loadUsers()
}

// 查看用户详情
const viewUserDetail = (user) => {
  selectedUser.value = user
  detailDialogVisible.value = true
}

// 打开VIP设置对话框
const openVipDialog = (user) => {
  selectedUser.value = user
  vipForm.value = {
    vip_level: 1,
    months: 1
  }
  vipDialogVisible.value = true
}

// 计算VIP到期日期
const calculateExpireDate = () => {
  if (!vipForm.value.months) return '-'
  const date = new Date()
  date.setMonth(date.getMonth() + vipForm.value.months)
  return formatDate(date.toISOString())
}

// 确认设置VIP
const confirmSetVip = async () => {
  if (!selectedUser.value) return

  try {
    const response = await request.post(
      `/users/admin-users/${selectedUser.value.id}/set-vip/`,
      vipForm.value
    )

    ElMessage.success(response.detail)
    vipDialogVisible.value = false
    loadUsers()
  } catch (error) {
    console.error('设置VIP失败:', error)
    ElMessage.error(error.response?.data?.detail || '设置VIP失败')
  }
}

// 取消VIP
const cancelVip = async (user) => {
  try {
    await ElMessageBox.confirm(
      `确定要取消用户 ${user.username} 的VIP状态吗？`,
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const response = await request.post(`/users/admin-users/${user.id}/cancel-vip/`)
    ElMessage.success(response.detail)
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('取消VIP失败:', error)
      ElMessage.error(error.response?.data?.detail || '取消VIP失败')
    }
  }
}

// 切换用户激活状态
const toggleUserActive = async (user) => {
  try {
    const action = user.is_active ? '禁用' : '启用'
    await ElMessageBox.confirm(
      `确定要${action}用户 ${user.username} 的账户吗？`,
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const response = await request.post(`/users/admin-users/${user.id}/toggle-active/`)
    ElMessage.success(response.detail)
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('切换用户状态失败:', error)
      ElMessage.error(error.response?.data?.detail || '操作失败')
    }
  }
}

// 获取VIP标签类型
const getVipTagType = (vipStatus) => {
  switch (vipStatus) {
    case 'active': return 'success'
    case 'expired': return 'warning'
    default: return 'info'
  }
}

// 获取剩余天数
const getRemainingDays = (expireTime) => {
  if (!expireTime) return 0
  const now = new Date()
  const expire = new Date(expireTime)
  const diff = expire - now
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)))
}

// 获取剩余天数样式类
const getVipDaysClass = (expireTime) => {
  const days = getRemainingDays(expireTime)
  if (days <= 7) return 'vip-days-warning'
  if (days <= 30) return 'vip-days-notice'
  return 'vip-days-normal'
}

// 获取性别文本
const getGenderText = (gender) => {
  const genderMap = {
    'male': '男',
    'female': '女',
    'other': '其他'
  }
  return genderMap[gender] || '未设置'
}

// 格式化日期
const formatDate = (dateStr, type = 'full') => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  
  if (type === 'date') {
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    })
  }
  
  if (type === 'time') {
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }
  
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 表格行类名
const tableRowClassName = ({ row }) => {
  if (!row.is_active) return 'disabled-row'
  if (row.is_vip) return 'vip-row'
  return ''
}

// 组件挂载时加载数据
onMounted(() => {
  loadUsers()
  loadStats()
})
</script>

<style scoped>
.user-management-container {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
  position: relative;
}

/* 统计卡片 */
.stats-section {
  margin-bottom: 20px;
}

.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.3s;
  animation-duration: 0.6s;
}

.stat-card:hover {
  transform: translateY(-4px) scale(1.02);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 15px;
  color: #fff;
  font-size: 28px;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #333;
  line-height: 1;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #666;
}

/* 筛选区域 */
.filter-section {
  margin-bottom: 20px;
  padding: 20px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

/* 表格区域 */
.table-section {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  overflow: visible;
}

.table-section :deep(.el-table) {
  overflow: visible;
}

.table-section :deep(.el-table__body-wrapper) {
  overflow: visible !important;
}

.table-section :deep(.el-scrollbar__bar) {
  display: none !important;
}

.table-section :deep(.el-table__inner-wrapper) {
  overflow: visible !important;
}

/* 用户信息单元格 */
.user-info-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-avatar {
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.user-details {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.user-nickname {
  font-size: 13px;
  color: #666;
  margin-bottom: 2px;
}

.user-email {
  font-size: 12px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* VIP信息单元格 */
.vip-info-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.vip-expire {
  font-size: 12px;
  color: #666;
}

.vip-days {
  font-size: 12px;
  font-weight: 600;
}

.vip-days-normal {
  color: #67c23a;
}

.vip-days-notice {
  color: #e6a23c;
}

.vip-days-warning {
  color: #f56c6c;
}

/* 用户数据单元格 */
.user-stats-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #666;
}

.stat-item .el-icon {
  font-size: 14px;
  color: #409eff;
}

/* 时间单元格 */
.time-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.time-sub {
  font-size: 12px;
  color: #999;
}

/* 分页 */
.pagination-section {
  display: flex;
  justify-content: center;
  margin-top: 20px;
  padding: 20px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

/* 表格行样式 */
:deep(.el-table .vip-row) {
  background-color: #fffbf0;
}

:deep(.el-table .disabled-row) {
  background-color: #f5f5f5;
  color: #999;
}

:deep(.el-table .el-table__cell) {
  padding: 12px 0;
}

/* 对话框样式 */
.dialog-user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
}

.form-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

/* 用户详情对话框 */
.user-detail-content {
  padding: 0;
}

.detail-avatar-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 30px 20px;
  background: #667eea;
  border-radius: 12px;
  color: #fff;
}

.detail-username {
  font-size: 20px;
  font-weight: 600;
  margin-top: 8px;
  color: #fff;
}

.detail-stats-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 0;
}

.detail-stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  transition: all 0.3s;
}

.detail-stat-item:hover {
  background: #e8eaf0;
  transform: translateX(4px);
}

.detail-stat-item .stat-icon {
  font-size: 28px;
  color: #409eff;
}

.detail-stat-item .stat-info {
  flex: 1;
}

.detail-stat-item .stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #333;
  line-height: 1;
  margin-bottom: 4px;
}

.detail-stat-item .stat-label {
  font-size: 13px;
  color: #666;
}

.vip-days-badge {
  margin-left: 12px;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.vip-days-badge.vip-days-normal {
  background: #f0f9ff;
  color: #67c23a;
}

.vip-days-badge.vip-days-notice {
  background: #fef0e6;
  color: #e6a23c;
}

.vip-days-badge.vip-days-warning {
  background: #fef0f0;
  color: #f56c6c;
}

.text-muted {
  color: #999;
}

:deep(.el-dialog .el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-descriptions) {
  margin-top: 0;
}

:deep(.el-descriptions__title) {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}

:deep(.el-descriptions__label) {
  font-weight: 500;
}

:deep(.el-divider) {
  margin: 24px 0;
}
</style> 