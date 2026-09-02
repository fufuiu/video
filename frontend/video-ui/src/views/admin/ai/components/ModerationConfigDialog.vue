<template>
  <el-dialog 
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    :title="title"
    width="600px"
    @close="$emit('close')"
    append-to-body
  >
    <el-alert type="warning" :closable="false" show-icon>
      <template #title>视频将临时发送到阿里云内容安全服务</template>
      原视频仍保存在本地；审核时系统会把完整视频临时上传到私有 OSS，生成短期签名地址供阿里云读取，并在任务结束后立即尝试删除。
    </el-alert>
    <div class="review-notes">
      <p>审核策略由阿里云控制台统一管理，页面不再提供不会生效的阈值和抽帧参数。</p>
      <p>AI 返回的是标签匹配结果；中风险只表示待人工复核，不会自动认定违规。</p>
      <p>OSS 的生命周期规则会在即时清理失败时自动兜底删除临时对象。</p>
    </div>
    
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="$emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" :loading="loading" @click="$emit('confirm')">
          <el-icon><Cpu /></el-icon> 开始审核
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { Cpu } from '@element-plus/icons-vue';

defineProps({
  modelValue: Boolean,
  title: String,
  loading: Boolean
});

defineEmits(['update:modelValue', 'close', 'confirm']);
</script>

<style scoped>
.review-notes { margin-top: 18px; color: #606266; font-size: 14px; line-height: 1.7; }
.review-notes p { margin: 8px 0; }
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
