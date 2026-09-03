<template>
  <div class="ai-moderation-container animate__animated animate__fadeIn animate__faster">
    <PageHeader 
      title="AI 智能审核" 
      :breadcrumb="[{ label: '管理后台', path: '/admin' }, { label: 'AI 审核' }]"
      class="animate__animated animate__fadeInDown animate__faster"
    >
      <template #actions>
        <div class="header-actions animate__animated animate__fadeInRight animate__faster">
          <el-button @click="helpVisible = true" type="info" plain>
            <el-icon><QuestionFilled /></el-icon> 结果说明
          </el-button>
          <el-select v-model="statusFilter" placeholder="审核状态" clearable @change="handleFilterChange" style="width: 140px;">
            <el-option label="全部状态" value="" />
            <el-option label="待审核" value="pending" />
            <el-option label="审核中" value="processing" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
          </el-select>
          <el-select v-model="resultFilter" placeholder="审核结果" clearable @change="handleFilterChange" style="width: 140px;">
            <el-option label="全部结果" value="" />
            <el-option label="安全" value="safe" />
            <el-option label="待人工复核" value="uncertain" />
            <el-option label="不安全" value="unsafe" />
          </el-select>
          <el-button type="primary" @click="batchModerate" :disabled="selectedVideos.length === 0">
            <el-icon><Cpu /></el-icon> 批量审核 ({{ selectedVideos.length }})
          </el-button>
        </div>
      </template>
    </PageHeader>

    <StatsCards :stats="stats" class="animate__animated animate__fadeInUp animate__faster" />

    <!-- 审核列表 -->
    <div class="moderation-list animate__animated animate__fadeInUp animate__fast">
      <el-table 
        v-loading="loading" 
        :data="moderationList" 
        @selection-change="handleSelectionChange"
        style="width: 100%"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column label="视频" width="300">
          <template #default="{ row }">
            <div class="video-cell">
              <el-image 
                :src="row.video.thumbnail || '/placeholder.jpg'" 
                fit="cover" 
                class="video-thumb"
              >
                <template #error>
                  <div class="image-error">
                    <el-icon><Picture /></el-icon>
                  </div>
                </template>
              </el-image>
              <div class="video-info">
                <div class="video-title">{{ row.video.title }}</div>
                <div class="video-meta">
                  <span>{{ row.video.user?.username }}</span>
                  <span>{{ formatDate(row.video.created_at) }}</span>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="审核状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="审核结果" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.effective_result || row.result" :type="getResultType(row.effective_result || row.result)">
              {{ getResultText(row.effective_result || row.result) }}
            </el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        
        <el-table-column label="标签匹配置信度" width="140" align="center">
          <template #default="{ row }">
            <span v-if="row.flagged_frames?.length > 0">
              {{ ((row.label_confidence ?? row.confidence) * 100).toFixed(1) }}%
            </span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        
        <el-table-column label="主要命中原因" min-width="240">
          <template #default="{ row }">
            <span v-if="row.flagged_frames?.length">
              {{ row.flagged_frames[0].label_text || row.flagged_frames[0].label || '疑似风险内容' }}
            </span>
            <span v-else-if="row.status === 'completed'" class="text-muted">未命中标签</span>
            <span v-else class="text-muted">待审核</span>
          </template>
        </el-table-column>
        
        <el-table-column label="命中事件" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.flagged_frames?.length > 0" type="warning" size="small">
              {{ row.flagged_frames.length }} 条
            </el-tag>
            <span v-else class="text-muted">无</span>
          </template>
        </el-table-column>
        
        <el-table-column label="审核时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.updated_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button 
              v-if="row.status === 'pending' || row.status === 'failed'" 
              type="primary" 
              size="small" 
              @click="moderateVideo(row)"
            >
              <el-icon><Cpu /></el-icon> 开始审核
            </el-button>
            <el-button 
              v-if="row.status === 'completed'" 
              type="info" 
              size="small" 
              @click="viewDetail(row)"
            >
              <el-icon><View /></el-icon> 查看详情
            </el-button>
            <el-button 
              v-if="row.status === 'processing'" 
              type="warning" 
              size="small" 
              disabled
            >
              <el-icon><Loading /></el-icon> 审核中
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <div class="pagination-container" v-if="total > 0">
      <el-pagination 
        v-model:current-page="currentPage" 
        v-model:page-size="pageSize" 
        :page-sizes="[10, 20, 50, 100]" 
        layout="total, sizes, prev, pager, next, jumper" 
        :total="total" 
        @size-change="handleSizeChange" 
        @current-change="handleCurrentChange" 
      />
    </div>

    <ModerationConfigDialog
      v-model="configVisible"
      :title="configTitle"
      :loading="loading"
      @confirm="confirmModerate"
    />

    <ModerationDetailDialog
      v-model="detailVisible"
      :detail="currentDetail"
      :get-status-type="getStatusType"
      :get-status-text="getStatusText"
      :get-result-type="getResultType"
      :get-result-text="getResultText"
      :format-date-time="formatDateTime"
      :format-time="formatTime"
      @confirm-safe="handleReviewAction('confirmed_safe')"
      @confirm-false-positive="handleReviewAction('false_positive')"
      @confirm-violation="handleReviewAction('confirmed_violation')"
      @revoke-review="handleReviewAction('revoke')"
      @re-moderate="handleReModerate"
    />

    <HelpDialog v-model="helpVisible" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue';
import { 
  Cpu, View, Picture, QuestionFilled, Loading
} from '@element-plus/icons-vue';
import PageHeader from '@/components/common/PageHeader.vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { 
  getAIModerationList, 
  getAIModerationDetail,
  submitAIModeration, 
  batchAIModeration,
  getAITaskStatus,
  submitAIReview,
  revokeAIReview,
  reModerateVideo
} from '@/api/admin';

// 子组件
import StatsCards from './components/StatsCards.vue';
import ModerationConfigDialog from './components/ModerationConfigDialog.vue';
import ModerationDetailDialog from './components/ModerationDetailDialog.vue';
import HelpDialog from './components/HelpDialog.vue';

// 数据
const loading = ref(false);
const moderationList = ref([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const statusFilter = ref('');
const resultFilter = ref('');
const selectedVideos = ref([]);
const detailVisible = ref(false);
const helpVisible = ref(false);
const configVisible = ref(false);
const configTitle = ref('确认云端 AI 审核');
const currentDetail = ref(null);
const currentModerationVideo = ref(null);
const taskPollTimers = new Map();
const TASK_POLL_INTERVAL = 1500;

// 统计数据
const stats = reactive({
  pending: 0,
  processing: 0,
  safe: 0,
  uncertain: 0,
  unsafe: 0
});

// 获取审核列表
const fetchModerationList = async () => {
  loading.value = true;
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    };
    if (statusFilter.value) params.status = statusFilter.value;
    if (resultFilter.value) params.result = resultFilter.value;

    const response = await getAIModerationList(params);

    moderationList.value = response.results || [];
    total.value = response.count || 0;
    
    // 更新统计数据
    if (response.stats) {
      Object.assign(stats, response.stats);
    }
  } catch (error) {
    console.error('获取审核列表失败:', error);
    ElMessage.error('获取审核列表失败');
  } finally {
    loading.value = false;
  }
};

const markModerationsProcessing = (videoIds) => {
  const ids = new Set(videoIds.map(id => String(id)));
  moderationList.value = moderationList.value.map(item => {
    if (!ids.has(String(item.video?.id))) return item;
    return Object.assign({}, item, {
      status: 'processing',
      result: null,
      effective_result: null,
      error_message: '',
      updated_at: new Date().toISOString()
    });
  });
};

const stopTaskPolling = (taskId) => {
  const timer = taskPollTimers.get(taskId);
  if (timer) window.clearTimeout(timer);
  taskPollTimers.delete(taskId);
};

const pollModerationTask = async (taskId) => {
  try {
    const task = await getAITaskStatus(taskId);
    if (['succeeded', 'failed', 'cancelled'].includes(task.status)) {
      stopTaskPolling(taskId);
      await fetchModerationList();

      // 批量任务完成后继续跟踪它创建的每个单视频审核任务。
      if (task.status === 'succeeded' && Array.isArray(task.result)) {
        task.result.forEach(item => {
          if (item.task_id && item.status === 'submitted') {
            trackModerationTask(item.task_id);
          }
        });
      }
      return;
    }
  } catch (error) {
    console.warn('审核任务状态查询失败，将刷新列表:', error);
    stopTaskPolling(taskId);
    await fetchModerationList();
    return;
  }

  const timer = window.setTimeout(() => pollModerationTask(taskId), TASK_POLL_INTERVAL);
  taskPollTimers.set(taskId, timer);
};

function trackModerationTask(taskId) {
  if (!taskId || taskPollTimers.has(taskId)) return;
  taskPollTimers.set(taskId, null);
  void pollModerationTask(taskId);
}

// 审核单个视频
const moderateVideo = (row) => {
  currentModerationVideo.value = row;
  configTitle.value = '确认云端 AI 审核 - ' + row.video.title;
  configVisible.value = true;
};

// 批量审核
const batchModerate = () => {
  if (selectedVideos.value.length === 0) {
    ElMessage.warning('请先选择要审核的视频');
    return;
  }
  currentModerationVideo.value = null;
  configTitle.value = '确认批量云端审核 (' + selectedVideos.value.length + ' 个视频)';
  configVisible.value = true;
};

// 确认审核
const confirmModerate = async () => {
  try {
    loading.value = true;
    configVisible.value = false;
    let response;
    let videoIds;
    
    if (currentModerationVideo.value) {
      videoIds = [currentModerationVideo.value.video.id];
      response = await submitAIModeration({
        video_id: currentModerationVideo.value.video.id
      });
    } else {
      videoIds = selectedVideos.value.map(function(v) { return v.video.id; });
      response = await batchAIModeration({
        video_ids: videoIds
      });
    }

    // 接口接单后立即回写当前行，不等待 Worker 或下一次手动刷新。
    markModerationsProcessing(videoIds);
    ElMessage.success('审核任务已提交');
    await fetchModerationList();
    trackModerationTask(response.task_id);
    selectedVideos.value = [];
  } catch (error) {
    console.error('提交审核任务失败:', error);
    ElMessage.error('提交审核任务失败');
    await fetchModerationList();
  } finally {
    loading.value = false;
  }
};

// 查看详情
const viewDetail = async (row) => {
  try {
    const response = await getAIModerationDetail(row.id);
    currentDetail.value = response;
    detailVisible.value = true;
  } catch (error) {
    console.error('获取审核详情失败:', error);
    ElMessage.error('获取审核详情失败');
  }
};

// 提交人工审核/撤销审核
const handleReviewAction = async (action) => {
  try {
    loading.value = true;
    if (action === 'revoke') {
      await ElMessageBox.confirm('确认撤销人工结论并恢复待处理状态？', '撤销人工结论', { type: 'warning' });
      await revokeAIReview({ moderation_id: currentDetail.value.id });
      ElMessage.success('已撤销人工结论');
    } else {
      const isSafe = action === 'confirmed_safe';
      const isFalsePositive = action === 'false_positive';
      const prompt = await ElMessageBox.prompt(
        isSafe
          ? '确认视频安全并通过？可填写判断依据。'
          : isFalsePositive
            ? '确认这是 AI 误报并通过该视频？可填写判断依据。'
            : '确认视频违规并拒绝该视频？请填写判断依据。',
        isSafe ? '确认安全' : isFalsePositive ? '确认误报' : '确认违规',
        {
          type: isFalsePositive ? 'success' : 'warning',
          inputPlaceholder: '人工复核备注（可选）',
          inputValidator: value => value.length <= 500 || '备注不能超过 500 个字符'
        }
      );
      await submitAIReview({
        moderation_id: currentDetail.value.id,
        action,
        remark: prompt.value || ''
      });
      ElMessage.success(
        isSafe
          ? '已确认安全并通过视频'
          : isFalsePositive
            ? '已确认误报并通过视频'
            : '已确认违规并拒绝视频'
      );
    }
    
    detailVisible.value = false;
    fetchModerationList();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败');
    }
  } finally {
    loading.value = false;
  }
};

// 重新审核
const handleReModerate = async () => {
  try {
    await ElMessageBox.confirm('重新审核会清除现有人工结论，确认继续？', '重新 AI 审核', { type: 'warning' });
    loading.value = true;
    const response = await reModerateVideo({ moderation_id: currentDetail.value.id });
    markModerationsProcessing([currentDetail.value.video.id]);
    ElMessage.success('重新审核任务已提交');
    detailVisible.value = false;
    await fetchModerationList();
    trackModerationTask(response.task_id);
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('重新审核提交失败');
  } finally {
    loading.value = false;
  }
};

// 选择变化
const handleSelectionChange = (selection) => {
  selectedVideos.value = selection.filter(
    item => item.status === 'pending' || item.status === 'failed'
  );
};

// 筛选变化
const handleFilterChange = () => {
  currentPage.value = 1;
  fetchModerationList();
};

// 分页
const handleSizeChange = () => {
  fetchModerationList();
};

const handleCurrentChange = () => {
  fetchModerationList();
};

// 工具函数
const getStatusType = (status) => {
  const map = {
    pending: 'info',
    processing: 'warning',
    completed: 'success',
    failed: 'danger'
  };
  return map[status] || 'info';
};

const getStatusText = (status) => {
  const map = {
    pending: '待审核',
    processing: '审核中',
    completed: '已完成',
    failed: '失败'
  };
  return map[status] || '未知';
};

const getResultType = (result) => {
  const map = {
    safe: 'success',
    unsafe: 'danger',
    uncertain: 'warning'
  };
  return map[result] || 'info';
};

const getResultText = (result) => {
  const map = {
    safe: '安全',
    unsafe: '不安全',
    uncertain: '待人工复核'
  };
  return map[result] || '未知';
};

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${month}-${day}`;
};

const formatDateTime = (dateStr) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
};

const formatTime = (seconds) => {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
};

onMounted(() => {
  fetchModerationList();
});

onBeforeUnmount(() => {
  taskPollTimers.forEach(timer => {
    if (timer) window.clearTimeout(timer);
  });
  taskPollTimers.clear();
});
</script>

<style scoped>
.ai-moderation-container {
  padding: 20px;
  min-height: 100%;
  position: relative;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

/* 列表容器 */
.moderation-list {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

/* 视频单元格 */
.video-cell {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 8px 0;
}

.video-thumb {
  width: 160px;
  height: 90px;
  border-radius: 6px;
  flex-shrink: 0;
  cursor: pointer;
  transition: opacity 0.3s;
}

.video-thumb:hover {
  opacity: 0.8;
}

.image-error {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background: #f5f5f5;
  color: #ccc;
  font-size: 24px;
}

.video-info {
  flex: 1;
  min-width: 0;
}

.video-title {
  font-size: 14px;
  font-weight: 500;
  color: #18191c;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.4;
}

.video-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #9499a0;
}

.text-muted {
  color: #9499a0;
}

/* 风险评分列 */
.risk-scores {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0;
}

.score-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.score-label {
  font-size: 12px;
  color: #61666d;
}

.score-item .el-progress {
  width: 180px;
}

.score-value {
  font-size: 12px;
  color: #61666d;
  font-weight: 500;
  margin-top: 2px;
}

/* 分页容器 */
.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  background: #fff;
  padding: 12px;
  border-radius: 8px;
}
</style>
