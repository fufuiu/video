<template>
  <div class="title-bar" :class="{ 'is-maximized': isMaximized }">
    <div class="title-bar-drag">
      <div class="title-bar-icon">
        <slot name="icon">
          <el-icon :size="20"><VideoPlay /></el-icon>
        </slot>
      </div>
      <div class="title-bar-title">{{ title }}</div>
      
      <!-- 导航按钮 -->
      <div class="nav-controls" v-if="isElectron">
        <button 
          class="nav-btn" 
          :disabled="!canGoBack" 
          @click="goBack"
          title="后退"
        >
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <button 
          class="nav-btn" 
          :disabled="!canGoForward" 
          @click="goForward"
          title="前进"
        >
          <el-icon><ArrowRight /></el-icon>
        </button>
        <button 
          class="nav-btn" 
          @click="refresh"
          title="刷新"
        >
          <el-icon><Refresh /></el-icon>
        </button>
      </div>
    </div>
    <div class="title-bar-controls">
      <button class="title-bar-btn minimize" @click="minimize" title="最小化">
        <svg width="12" height="12" viewBox="0 0 12 12">
          <rect fill="currentColor" width="10" height="1" x="1" y="6" />
        </svg>
      </button>
      <button class="title-bar-btn maximize" @click="toggleMaximize" :title="isMaximized ? '还原' : '最大化'">
        <svg v-if="!isMaximized" width="12" height="12" viewBox="0 0 12 12">
          <rect stroke="currentColor" fill="none" width="9" height="9" x="1.5" y="1.5" stroke-width="1" />
        </svg>
        <svg v-else width="12" height="12" viewBox="0 0 12 12">
          <rect stroke="currentColor" fill="none" width="5" height="5" x="1.5" y="5.5" stroke-width="1" />
          <rect stroke="currentColor" fill="var(--bg-color, #fff)" width="5" height="5" x="5.5" y="1.5" stroke-width="1" />
        </svg>
      </button>
      <button class="title-bar-btn close" @click="close" title="关闭">
        <svg width="12" height="12" viewBox="0 0 12 12">
          <path fill="currentColor" d="M6.707 6l3.147-3.146a.5.5 0 0 0-.708-.708L6 5.293 2.854 2.146a.5.5 0 0 0-.708.708L5.293 6l-3.147 3.146a.5.5 0 0 0 .708.708L6 6.707l3.146 3.147a.5.5 0 0 0 .708-.708L6.707 6z" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { VideoPlay, ArrowLeft, ArrowRight, Refresh } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

defineProps({
  title: {
    type: String,
    default: 'Video App'
  }
})

const isMaximized = ref(false)
const canGoBack = ref(false)
const canGoForward = ref(false)
const router = useRouter()

// 检查是否在 Electron 环境中
const isElectron = window.electronAPI !== undefined

const checkNavState = async () => {
  if (isElectron) {
    canGoBack.value = await window.electronAPI.canGoBack()
    canGoForward.value = await window.electronAPI.canGoForward()
  }
}

const goBack = () => {
  if (isElectron) {
    window.electronAPI.goBack()
  }
}

const goForward = () => {
  if (isElectron) {
    window.electronAPI.goForward()
  }
}

const refresh = () => {
  location.reload()
}

const minimize = () => {
  if (isElectron) {
    window.electronAPI.minimizeWindow()
  }
}

const toggleMaximize = () => {
  if (isElectron) {
    window.electronAPI.maximizeWindow()
    // 更新状态
    setTimeout(async () => {
      isMaximized.value = await window.electronAPI.isMaximized()
    }, 100)
  }
}

const close = () => {
  if (isElectron) {
    window.electronAPI.closeWindow()
  }
}

let timer
onMounted(async () => {
  if (isElectron) {
    isMaximized.value = await window.electronAPI.isMaximized()
    checkNavState()
    // 定时轮询导航状态（Electron webContents 状态变化较难监听，简单轮询最稳健）
    timer = setInterval(checkNavState, 500)
  }
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.title-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 32px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  user-select: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
}

.title-bar-drag {
  display: flex;
  align-items: center;
  flex: 1;
  -webkit-app-region: drag;
  padding-left: 12px;
}

.title-bar-icon {
  display: flex;
  align-items: center;
  margin-right: 8px;
}

.title-bar-title {
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.5px;
  margin-right: 20px;
}

.nav-controls {
  display: flex;
  align-items: center;
  -webkit-app-region: no-drag;
  gap: 4px;
}

.nav-btn {
  background: transparent;
  border: none;
  color: #fff;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.nav-btn:hover:not(:disabled) {
  background-color: rgba(255, 255, 255, 0.2);
}

.nav-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.title-bar-controls {
  display: flex;
  -webkit-app-region: no-drag;
}

.title-bar-btn {
  width: 46px;
  height: 32px;
  border: none;
  background: transparent;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.15s;
}

.title-bar-btn:hover {
  background-color: rgba(255, 255, 255, 0.15);
}

.title-bar-btn.close:hover {
  background-color: #e81123;
}

.title-bar.is-maximized {
  padding-top: 0;
}
</style>

<style scoped>
.title-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 32px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  user-select: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
}

.title-bar-drag {
  display: flex;
  align-items: center;
  flex: 1;
  -webkit-app-region: drag;
  padding-left: 12px;
}

.title-bar-icon {
  display: flex;
  align-items: center;
  margin-right: 8px;
}

.title-bar-title {
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.title-bar-controls {
  display: flex;
  -webkit-app-region: no-drag;
}

.title-bar-btn {
  width: 46px;
  height: 32px;
  border: none;
  background: transparent;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.15s;
}

.title-bar-btn:hover {
  background-color: rgba(255, 255, 255, 0.15);
}

.title-bar-btn.close:hover {
  background-color: #e81123;
}

.title-bar.is-maximized {
  padding-top: 0;
}
</style>
