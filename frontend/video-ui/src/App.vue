<template>
  <div class="app-wrapper" :class="{ 'is-electron': isElectron, 'is-fullscreen': isFullScreen }">
    <!-- 无边框模式下的顶部拖拽区域 -->
    <div v-if="isElectron && !isFullScreen" class="electron-drag-handle"></div>

    <div class="main-container">
      <router-view v-slot="{ Component }">
        <component :is="Component" :key="$route.fullPath" />
      </router-view>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const isElectron = ref(false);
const isFullScreen = ref(false);

// 检测是否在 Electron 环境中
const checkElectron = () => {
  isElectron.value = window.electronAPI !== undefined;
};

// 轮询检测全屏状态（因为窗口大小变化时 transition 效果更好）
const checkFullScreen = async () => {
  if (isElectron.value && window.electronAPI.isFullScreen) {
    isFullScreen.value = await window.electronAPI.isFullScreen();
  }
};

let timer;
onMounted(() => {
  checkElectron();
  if (isElectron.value) {
    timer = setInterval(checkFullScreen, 500);
  }
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<style>
body {
  margin: 0;
  padding: 0;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background-color: var(--bg-color, #fff);
  color: var(--text-color, #333);
  overflow-x: hidden;
  overflow-y: auto;
  transition: background-color var(--motion-normal, 220ms) ease, color var(--motion-normal, 220ms) ease;
}

#app {
  min-height: 100dvh;
  width: 100vw;
}

.app-wrapper {
  min-height: 100dvh;
  width: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
  /* 添加平滑过渡动画 */
  transition: background-color var(--motion-normal, 220ms) ease;
}

/* 全屏状态下的特殊样式 */
.is-fullscreen {
  transform: scale(1);
}

.is-fullscreen .main-container {
  padding: 0;
}

/* 顶部拖拽区域 */
.electron-drag-handle {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 30px;
  -webkit-app-region: drag;
  z-index: 9998;
}

.main-container {
  flex: 1;
  width: 100%;
  min-height: 0;
  overflow-y: auto;
  position: relative;
  /* 内容平滑过渡 */
  transition: padding 0.5s ease;
}
</style>
