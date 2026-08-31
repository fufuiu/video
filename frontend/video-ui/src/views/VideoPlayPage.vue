<template>
  <div class="video-play-page">
    <div class="video-container">
      <!-- 视频播放器 -->
      <VideoPlayer
        v-if="videoData.hls_file"
        :src="getVideoUrl(videoData.hls_file)"
        :poster="videoData.thumbnail"
        :video-id="videoData.id"
        @timeupdate="handleTimeUpdate"
        @ended="handleVideoEnded"
      />
      
      <!-- 加载中 -->
      <div v-else-if="loading" class="loading">
        <div class="spinner"></div>
        <p>视频加载中...</p>
      </div>
      
      <!-- 错误提示 -->
      <div v-else class="error">
        <p>视频暂时无法播放</p>
        <p v-if="videoData.status === 'processing'">视频正在处理中，请稍后再试</p>
        <p v-else-if="videoData.status === 'pending'">视频正在审核中</p>
      </div>
    </div>

    <!-- 视频信息 -->
    <div class="video-info">
      <h1>{{ videoData.title }}</h1>
      <div class="meta">
        <span>{{ formatViews(videoData.views_count) }} 次观看</span>
        <span>{{ formatDate(videoData.created_at) }}</span>
      </div>
      <div class="actions">
        <button @click="handleLike" :class="{ active: isLiked }">
          👍 {{ videoData.likes_count }}
        </button>
        <button @click="handleCollect" :class="{ active: isCollected }">
          ⭐ 收藏
        </button>
      </div>
      <div class="description">
        <p>{{ videoData.description }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import VideoPlayer from '@/components/VideoPlayer.vue'
import service from '@/api/user'

const route = useRoute()
const videoId = route.params.id

const videoData = ref({})
const loading = ref(true)
const isLiked = ref(false)
const isCollected = ref(false)

// 获取视频详情
const fetchVideoDetail = async () => {
  try {
    loading.value = true
    const response = await service.get(`/videos/videos/${videoId}/`)
    videoData.value = response
    
    // 检查是否已点赞/收藏
    checkLikeStatus()
    checkCollectStatus()
  } catch (error) {
    console.error('获取视频详情失败:', error)
  } finally {
    loading.value = false
  }
}

// 获取视频 URL
const getVideoUrl = (hlsPath) => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  return `${baseUrl}/media/${hlsPath}`
}

// 格式化观看次数
const formatViews = (count) => {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万`
  }
  return count
}

// 格式化日期
const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 30) return `${days}天前`
  if (days < 365) return `${Math.floor(days / 30)}个月前`
  return `${Math.floor(days / 365)}年前`
}

// 处理播放进度更新
const handleTimeUpdate = ({ currentTime, duration, videoId }) => {
  // 每 10 秒上报一次播放进度
  if (Math.floor(currentTime) % 10 === 0) {
    reportProgress(videoId, currentTime)
  }
}

// 上报播放进度
const reportProgress = async (videoId, currentTime) => {
  try {
    await service.post(`/videos/videos/${videoId}/record-view/`, {
      watched_duration: currentTime
    })
  } catch (error) {
    console.error('上报播放进度失败:', error)
  }
}

// 处理视频播放结束
const handleVideoEnded = ({ videoId }) => {
  // 可以推荐下一个视频
}

// 点赞
const handleLike = async () => {
  try {
    if (isLiked.value) {
      await service.delete(`/videos/videos/${videoId}/unlike/`)
      videoData.value.likes_count--
    } else {
      await service.post(`/videos/videos/${videoId}/like/`)
      videoData.value.likes_count++
    }
    isLiked.value = !isLiked.value
  } catch (error) {
    console.error('点赞操作失败:', error)
  }
}

// 收藏
const handleCollect = async () => {
  try {
    if (isCollected.value) {
      await service.delete(`/videos/videos/${videoId}/uncollect/`)
    } else {
      await service.post(`/videos/videos/${videoId}/collect/`)
    }
    isCollected.value = !isCollected.value
  } catch (error) {
    console.error('收藏操作失败:', error)
  }
}

// 检查点赞状态
const checkLikeStatus = async () => {
  try {
    const response = await service.get(`/videos/videos/${videoId}/is-liked/`)
    isLiked.value = response.is_liked
  } catch (error) {
    console.error('检查点赞状态失败:', error)
  }
}

// 检查收藏状态
const checkCollectStatus = async () => {
  try {
    const response = await service.get(`/videos/videos/${videoId}/is-collected/`)
    isCollected.value = response.is_collected
  } catch (error) {
    console.error('检查收藏状态失败:', error)
  }
}

onMounted(() => {
  fetchVideoDetail()
})
</script>

<style scoped>
.video-play-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.video-container {
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 20px;
}

.loading,
.error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  color: #fff;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 4px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.video-info {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.video-info h1 {
  font-size: 24px;
  margin-bottom: 10px;
}

.meta {
  display: flex;
  gap: 20px;
  color: #666;
  font-size: 14px;
  margin-bottom: 15px;
}

.actions {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.actions button {
  padding: 8px 20px;
  border: 1px solid #ddd;
  border-radius: 20px;
  background: #fff;
  cursor: pointer;
  transition: all 0.3s;
}

.actions button:hover {
  background: #f5f5f5;
}

.actions button.active {
  background: #1890ff;
  color: #fff;
  border-color: #1890ff;
}

.description {
  color: #333;
  line-height: 1.6;
}
</style>
