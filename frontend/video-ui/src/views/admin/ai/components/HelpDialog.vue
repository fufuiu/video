<template>
  <el-dialog 
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="AI 审核结果说明"
    width="800px"
    append-to-body
  >
    <div class="help-content">
      <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
        <template #title>
          <div style="font-size: 15px; line-height: 1.8;">
            <strong>核心概念</strong><br/>
            百分比表示供应商对某个标签的匹配置信度，不是整个视频的危险概率。
          </div>
        </template>
      </el-alert>

      <h3 style="margin-top: 24px;">总体结论</h3>
      <div class="help-section">
        <div class="help-item">
          <h4>安全</h4>
          <p>供应商没有返回需要处理的标签，可以自动通过。</p>
        </div>
        <div class="help-item">
          <h4>待人工复核</h4>
          <p>供应商返回低或中风险标签，需要结合命中画面判断，不能直接认定违规。</p>
        </div>
        <div class="help-item">
          <h4>不安全</h4>
          <p>供应商返回高风险结论，仍保留人工确认和审计记录。</p>
        </div>
      </div>
      <el-alert type="warning" :closable="false" show-icon>
        教程界面小字、人名、新闻截图和代码字符串都可能误报。请查看命中时间段和截图，再选择“确认误报”或“确认违规”。
      </el-alert>
    </div>
    <template #footer>
      <el-button type="primary" @click="$emit('update:modelValue', false)">我知道了</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
defineProps({
  modelValue: Boolean
});
defineEmits(['update:modelValue']);
</script>

<style scoped>
.help-content { padding: 10px; }
.help-item { margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 4px; }
.help-item h4 { margin: 0 0 8px 0; }
.help-item p { margin: 0; font-size: 14px; color: #606266; }
</style>
