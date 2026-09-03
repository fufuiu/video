<template>
  <div class="top-bar" :class="{ 'hidden': isCleanMode }">
    <div class="top-left">
      <button type="button" class="back-btn" aria-label="返回" title="返回" @click="$emit('go-back')">
        <el-icon><ArrowLeft /></el-icon>
      </button>
    </div>
    
    <div class="top-right" v-if="!isOwnVideo">
      <button type="button" class="top-btn" aria-label="更多操作" title="更多操作" :aria-expanded="showMenu" aria-haspopup="true" @click="showMenu = !showMenu">
        <el-icon><MoreFilled /></el-icon>
      </button>
      
      <transition name="fade">
        <div class="more-menu" v-if="showMenu" @click.stop>
          <button type="button" class="menu-item" @click="handleReport">
            <el-icon><WarningFilled /></el-icon>
            <span>举报</span>
          </button>
          <button type="button" class="menu-item" @click="handleNotInterested">
            <el-icon><CircleClose /></el-icon>
            <span>不感兴趣</span>
          </button>
        </div>
      </transition>
    </div>
    
    <!-- 举报对话框 -->
    <ReportDialog
      v-model:show="showReportDialog"
      :video-id="videoId"
      @success="handleReportSuccess"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { ArrowLeft, MoreFilled, WarningFilled, CircleClose } from '@element-plus/icons-vue';
import ReportDialog from './ReportDialog.vue';

defineProps({
  isCleanMode: Boolean,
  isOwnVideo: Boolean,
  videoId: [String, Number]
});

const emit = defineEmits(['go-back', 'report', 'not-interested']);

const showMenu = ref(false);
const showReportDialog = ref(false);

const handleReport = () => {
  showMenu.value = false;
  showReportDialog.value = true;
};

const handleNotInterested = () => {
  showMenu.value = false;
  emit('not-interested');
};

const handleReportSuccess = () => {
  emit('report');
};
</script>

<style scoped>
.top-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: transparent;
  z-index: 100;
  transition: opacity 0.3s, transform 0.3s;
}

.top-bar.hidden {
  opacity: 0;
  transform: translateY(-20px);
  pointer-events: none;
}

.top-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn,
.top-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #202127;
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.back-btn:hover,
.top-btn:hover {
  background: #303139;
  border-color: rgba(255, 255, 255, 0.55);
}

.top-right {
  position: relative;
}

.more-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: #1d1f25;
  border: 1px solid #3b3d46;
  border-radius: 8px;
  padding: 8px 0;
  min-width: 140px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  font: inherit;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.menu-item:hover {
  background: #30323a;
}

.back-btn:focus-visible,
.top-btn:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}

.menu-item .el-icon {
  font-size: 16px;
  color: rgba(255,255,255,0.7);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
