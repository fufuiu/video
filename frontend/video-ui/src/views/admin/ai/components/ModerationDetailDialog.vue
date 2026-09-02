<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="AI 审核详情"
    width="920px"
    destroy-on-close
    @close="$emit('close')"
    append-to-body
  >
    <div v-if="detail" class="detail-content">
      <section class="detail-section" v-if="detail.video">
        <h3>视频信息</h3>
        <div class="video-detail">
          <el-image
            :src="detail.video.thumbnail || '/placeholder.jpg'"
            fit="cover"
            class="video-cover"
          >
            <template #error>
              <div class="image-error"><el-icon><Picture /></el-icon></div>
            </template>
          </el-image>
          <div class="video-detail-info">
            <h4>{{ detail.video.title || '未知标题' }}</h4>
            <p>上传者：{{ detail.video.user?.username || '未知' }}</p>
            <p>上传时间：{{ detail.video.created_at ? formatDateTime(detail.video.created_at) : '未知' }}</p>
          </div>
        </div>
      </section>

      <el-divider />

      <section class="detail-section">
        <h3>总体决策</h3>
        <div class="result-summary">
          <div class="result-item">
            <span class="label">任务状态</span>
            <el-tag :type="getStatusType(detail.status)">{{ getStatusText(detail.status) }}</el-tag>
          </div>
          <div class="result-item">
            <span class="label">当前结论</span>
            <el-tag :type="getResultType(detail.effective_result || detail.result)">
              {{ getResultText(detail.effective_result || detail.result) }}
            </el-tag>
          </div>
          <div class="result-item">
            <span class="label">最高标签匹配置信度</span>
            <span v-if="detail.flagged_frames?.length" class="value">
              {{ ((detail.label_confidence ?? detail.confidence) * 100).toFixed(2) }}%
            </span>
            <span v-else class="muted">没有命中标签</span>
          </div>
        </div>
        <el-alert type="info" :closable="false" show-icon class="confidence-note">
          标签匹配置信度只表示供应商对某个标签的把握，不代表整个视频的危险概率。
        </el-alert>
      </section>

      <el-divider v-if="detail.human_decision && detail.human_decision !== 'pending'" />

      <section
        v-if="detail.human_decision && detail.human_decision !== 'pending'"
        class="detail-section"
      >
        <h3>人工复核结论</h3>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="结论">
            <el-tag :type="detail.human_decision === 'confirmed_violation' ? 'danger' : 'success'">
              {{ getHumanDecisionText(detail.human_decision) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="复核人">
            {{ detail.human_reviewer?.username || '未知' }}
          </el-descriptions-item>
          <el-descriptions-item label="复核时间">
            {{ detail.human_reviewed_at ? formatDateTime(detail.human_reviewed_at) : '未知' }}
          </el-descriptions-item>
          <el-descriptions-item label="备注">
            {{ detail.human_review_remark || '无' }}
          </el-descriptions-item>
        </el-descriptions>
      </section>

      <el-divider v-if="detail.flagged_frames?.length" />

      <section v-if="detail.flagged_frames?.length" class="detail-section">
        <h3>命中事件（{{ detail.flagged_frames.length }}）</h3>
        <div class="flagged-events">
          <article v-for="(frame, index) in detail.flagged_frames" :key="index" class="event-card">
            <el-image
              v-if="frame.image_url"
              :src="frame.image_url"
              fit="cover"
              class="event-image"
              :preview-src-list="[frame.image_url]"
              preview-teleported
            />
            <div v-else class="event-image event-image-empty">截图提取失败</div>
            <div class="event-body">
              <div class="event-header">
                <strong>{{ frame.label_text || frame.label || '疑似风险内容' }}</strong>
                <el-tag :type="frame.risk_level === 'high' ? 'danger' : 'warning'" size="small">
                  {{ frame.risk_level_text || '待人工复核' }}
                </el-tag>
              </div>
              <p class="event-time">{{ formatRange(frame) }}</p>
              <p>标签匹配置信度：{{ ((frame.confidence || 0) * 100).toFixed(2) }}%</p>
              <p v-if="frame.source_frame_count > 1">
                已合并 {{ frame.source_frame_count }} 个连续命中帧
              </p>
              <p class="raw-label">原始标签：{{ frame.label || '未知' }}</p>
            </div>
          </article>
        </div>
      </section>

      <section v-else-if="detail.status === 'completed'" class="detail-section">
        <el-alert type="success" :closable="false" show-icon>没有检测到需要复核的标签。</el-alert>
      </section>

      <el-divider />

      <div class="detail-actions" v-if="detail.status === 'completed'">
        <template v-if="detail.human_decision === 'pending'">
          <el-button
            v-if="detail.result === 'safe'"
            type="success"
            @click="$emit('confirm-safe')"
          >确认安全并通过</el-button>
          <el-button
            v-else
            type="success"
            @click="$emit('confirm-false-positive')"
          >确认误报并通过</el-button>
          <el-button type="danger" @click="$emit('confirm-violation')">确认违规并拒绝</el-button>
        </template>
        <el-button v-else @click="$emit('revoke-review')">撤销人工结论</el-button>
        <el-button type="warning" plain @click="$emit('re-moderate')">重新 AI 审核</el-button>
      </div>

      <template v-if="detail.error_message">
        <el-divider />
        <section class="detail-section">
          <h3>错误信息</h3>
          <el-alert type="error" :closable="false">{{ detail.error_message }}</el-alert>
        </section>
      </template>
    </div>
  </el-dialog>
</template>

<script setup>
import { Picture } from '@element-plus/icons-vue';

const props = defineProps({
  modelValue: Boolean,
  detail: Object,
  getStatusType: Function,
  getStatusText: Function,
  getResultType: Function,
  getResultText: Function,
  formatDateTime: Function,
  formatTime: Function
});

defineEmits([
  'update:modelValue',
  'close',
  'confirm-safe',
  'confirm-false-positive',
  'confirm-violation',
  'revoke-review',
  're-moderate'
]);

const formatRange = (frame) => {
  const start = frame.start_time ?? frame.timestamp ?? 0;
  const end = frame.end_time ?? start;
  return end > start
    ? `${props.formatTime(start)}～${props.formatTime(end)}`
    : props.formatTime(start);
};

const getHumanDecisionText = decision => ({
  confirmed_safe: '确认安全',
  false_positive: '确认误报',
  confirmed_violation: '确认违规'
}[decision] || '未人工复核');
</script>

<style scoped>
.detail-content { padding: 10px; }
.detail-section { margin-bottom: 20px; }
.detail-section h3 { font-size: 16px; font-weight: 600; color: #18191c; margin: 0 0 16px; }
.video-detail { display: flex; gap: 16px; }
.video-cover { width: 200px; height: 112px; border-radius: 8px; }
.video-detail-info h4 { font-size: 16px; font-weight: 500; margin: 0 0 12px; }
.video-detail-info p { font-size: 14px; color: #61666d; margin: 6px 0; }
.result-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.result-item { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.result-item .label { font-size: 13px; color: #9499a0; }
.result-item .value { font-size: 18px; font-weight: 600; color: #18191c; }
.muted { color: #909399; }
.confidence-note { margin-top: 16px; }
.flagged-events { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 16px; }
.event-card { overflow: hidden; background: #f6f7f8; border: 1px solid #ebeef5; border-radius: 8px; }
.event-image { display: block; width: 100%; height: 190px; background: #ebeef5; }
.event-image-empty { display: flex; align-items: center; justify-content: center; color: #909399; }
.event-body { padding: 14px; color: #606266; font-size: 13px; }
.event-body p { margin: 6px 0; }
.event-header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; color: #303133; }
.event-time { font-weight: 600; color: #409eff; }
.raw-label { color: #909399; word-break: break-all; }
.detail-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 12px; }
.image-error { display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; background: #f5f5f5; color: #ccc; font-size: 32px; }

@media (max-width: 760px) {
  .result-summary { grid-template-columns: 1fr; }
  .flagged-events { grid-template-columns: 1fr; }
}
</style>
