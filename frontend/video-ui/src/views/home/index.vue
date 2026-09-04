<template>
  <div class="douyin-home">
    <!-- 顶部导航 -->
    <TopNav />

    <!-- 分类导航 -->
    <div class="category-bar">
      <div class="category-container" ref="categoryContainer">
        <button
          v-for="(category, index) in categories"
          :key="category.id"
          :ref="el => setCategoryRef(el, index)"
          class="category-tab"
          :class="{ active: activeCategory === category.id }"
          type="button"
          role="tab"
          :aria-selected="activeCategory === category.id"
          @click="handleCategoryChange(category.id, index)"
        >
          {{ category.name }}
        </button>
        <div class="category-indicator" :style="indicatorStyle"></div>
      </div>
    </div>

    <!-- 视频瀑布流 -->
    <div class="main-container">
      <div v-if="loading && videos.length === 0" class="loading-state" role="status" aria-live="polite">
        <div class="loading-spinner"></div>
        <p>加载中...</p>
      </div>

      <div v-else-if="errorMessage" class="empty-state error-state" role="alert">
        <el-icon class="empty-icon"><WarningFilled /></el-icon>
        <strong>内容加载失败</strong>
        <p>{{ errorMessage }}</p>
        <el-button type="primary" @click="retryCurrentView">重新加载</el-button>
      </div>

      <div v-else-if="videos.length === 0" class="empty-state">
        <el-icon class="empty-icon"><VideoCamera /></el-icon>
        <strong>这里还没有视频</strong>
        <p>换个频道看看，或者发布你的第一个作品。</p>
        <div class="empty-actions">
          <el-button v-if="activeCategory !== 'recommend'" type="primary" @click="handleCategoryChange('recommend', 1)">看看推荐</el-button>
          <el-button plain @click="goToCreate">开始创作</el-button>
        </div>
      </div>

      <div v-else class="video-waterfall">
        <div
          v-for="(video, index) in videos"
          :key="video.id"
          class="video-item"
          role="link"
          tabindex="0"
          :style="{ animationDelay: `${index * 0.05}s` }"
          @click="goToVideo(video.id)"
          @keydown.enter="goToVideo(video.id)"
          @keydown.space.prevent="goToVideo(video.id)"
          @mouseenter="handleVideoHover(video, true)"
          @mouseleave="handleVideoHover(video, false)"
        >
          <div class="video-cover-wrapper">
            <!-- 封面图 -->
            <el-image 
              v-show="!video.isHovering"
              :src="video.thumbnail"
              :alt="video.title"
              fit="cover"
              class="video-cover"
              lazy
            >
              <template #error>
                <div class="cover-error">
                  <el-icon><VideoCamera /></el-icon>
                </div>
              </template>
            </el-image>
            
            <!-- 预览视频 -->
            <video
              v-show="video.isHovering"
              :ref="el => setVideoRef(el, video.id)"
              class="video-preview"
              muted
              loop
              playsinline
            ></video>
            
            <!-- 播放时长 - 左下角 -->
            <div class="video-duration-overlay">
              <el-icon class="play-icon-small"><VideoPlay /></el-icon>
              <span>{{ formatDuration(video.duration) }}</span>
            </div>
            
            <!-- 分辨率标识 - 右上角 -->
            <div v-if="video.resolution_label" class="resolution-badge" :class="video.resolution_label.toLowerCase()">
              {{ video.resolution_label }}
            </div>
          </div>
          
          <div class="video-info-wrapper">
            <h3 class="video-title">{{ video.title }}</h3>
            <div class="video-meta-bottom">
              <button class="author-info" type="button" @click.stop="goToUser(video.user.id)">
                <el-avatar :size="16" :src="video.user.avatar">
                  <el-icon><User /></el-icon>
                </el-avatar>
                <span class="author-name">{{ video.user.display_name || video.user.last_name || video.user.username }}</span>
              </button>
              <div class="video-stats">
                <span>{{ formatNumber(video.views_count) }} 次观看</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 加载更多 -->
      <div v-if="hasMore && !loading" class="load-more-wrapper">
        <el-button 
          @click="loadMore" 
          :loading="loadingMore"
          type="primary"
        >
          {{ loadingMore ? '加载中...' : '加载更多' }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import TopNav from '@/components/common/TopNav.vue'
import { VideoCamera, VideoPlay, User, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import service from '@/api/user'
import { getToken } from '@/utils/auth'

const router = useRouter()

const activeCategory = ref('all')
const categories = ref([
  { id: 'all', name: '全部' },
  { id: 'recommend', name: '推荐' }
])
const videos = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const hasMore = ref(true)
const currentPage = ref(1)
const errorMessage = ref('')

const baseCategories = [
  { id: 'all', name: '全部' },
  { id: 'recommend', name: '推荐' },
  { id: 'popular', name: '热门' },
  { id: 'latest', name: '最新' }
]

// 分类导航相关
const categoryContainer = ref(null)
const categoryRefs = ref([])
const indicatorStyle = ref({
  width: '0px',
  transform: 'translateX(0px)'
})

// 视频预览相关
const videoRefs = ref({})
const hoverTimers = ref({})

const setCategoryRef = (el, index) => {
  if (el) {
    categoryRefs.value[index] = el
  }
}

const setVideoRef = (el, videoId) => {
  if (el) {
    videoRefs.value[videoId] = el
  }
}

const handleVideoHover = (video, isEnter) => {
  const videoId = video.id
  
  // 清除之前的定时器
  if (hoverTimers.value[videoId]) {
    clearTimeout(hoverTimers.value[videoId])
  }
  
  if (isEnter) {
    // 延迟 500ms 开始预览（避免快速划过时加载）
    hoverTimers.value[videoId] = setTimeout(() => {
      // 找到对应的视频对象并更新
      const index = videos.value.findIndex(v => v.id === videoId)
      if (index !== -1) {
        videos.value[index].isHovering = true
        playPreview(videos.value[index])
      }
    }, 500)
  } else {
    // 立即停止预览
    const index = videos.value.findIndex(v => v.id === videoId)
    if (index !== -1) {
      videos.value[index].isHovering = false
    }
    stopPreview(videoId)
  }
}

const playPreview = async (video) => {
  const videoElement = videoRefs.value[video.id]
  if (!videoElement || !video.hls_file) {
    return
  }
  
  try {
    // 构建完整的 HLS URL
    let hlsUrl = video.hls_file
    if (!hlsUrl.startsWith('http')) {
      // 处理相对路径
      const hlsParts = hlsUrl.split('/')
      if (hlsParts.length >= 3 && !hlsUrl.includes('master.m3u8')) {
        hlsUrl = `${hlsParts[0]}/${hlsParts[1]}/${hlsParts[2]}/master.m3u8`
      }
      hlsUrl = `http://localhost:8000/media/${hlsUrl}`
    }
    
    // 检查 hls.js 是否加载
    if (typeof Hls === 'undefined') {
      console.error('hls.js 未加载')
      return
    }
    
    // 使用 hls.js
    if (Hls.isSupported()) {
      const hls = new Hls({
        maxBufferLength: 5, // 只缓冲 5 秒
        maxMaxBufferLength: 5,
        maxBufferSize: 2 * 1000 * 1000, // 2MB
        enableWorker: true,
        lowLatencyMode: false,
      })
      
      hls.on(Hls.Events.ERROR, (event, data) => {
        // 只打印致命错误，忽略非致命的 buffer 问题
        if (data.fatal) {
          console.error('HLS 致命错误:', data)
        }
      })
      
      hls.loadSource(hlsUrl)
      hls.attachMedia(videoElement)
      
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        videoElement.play().catch(e => console.error('播放失败:', e))
      })
      
      // 保存 hls 实例用于清理
      videoElement._hls = hls
      
      // 5 秒后循环
      const checkTime = () => {
        if (videoElement.currentTime >= 5) {
          videoElement.currentTime = 0
        }
      }
      videoElement.addEventListener('timeupdate', checkTime)
      videoElement._checkTime = checkTime
      
    } else if (videoElement.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari 原生支持
      videoElement.src = hlsUrl
      await videoElement.play()
    } else {
      console.error('浏览器不支持 HLS')
    }
    
  } catch (error) {
    console.error('预览播放失败:', error)
  }
}

const stopPreview = (videoId) => {
  const videoElement = videoRefs.value[videoId]
  if (!videoElement) return
  
  try {
    videoElement.pause()
    videoElement.currentTime = 0
    
    // 移除事件监听
    if (videoElement._checkTime) {
      videoElement.removeEventListener('timeupdate', videoElement._checkTime)
      videoElement._checkTime = null
    }
    
    // 清理 hls.js 实例
    if (videoElement._hls) {
      videoElement._hls.destroy()
      videoElement._hls = null
    }
    
    // 清空 src
    videoElement.src = ''
    videoElement.load()
  } catch (error) {
    console.error('停止预览失败:', error)
  }
}

const fetchCategories = async () => {
  try {
    const response = await service.get('/videos/categories/')
    const categoryData = response.results || response || []
    
    // 确保分类数据有 id 和 name 字段
    const validCategories = categoryData.filter(cat => cat.id && cat.name)
    
    categories.value = [...baseCategories, ...validCategories.filter(cat => !baseCategories.some(base => base.id === cat.id))]
    
    console.log('获取到的分类:', categories.value)
  } catch (error) {
    console.error('获取分类失败:', error)
  }
}

const fetchVideos = async (page = 1) => {
  try {
    errorMessage.value = ''
    if (page === 1) {
      loading.value = true
    } else {
      loadingMore.value = true
    }

    const params = {
      page,
      page_size: 20,
      ordering: '-created_at'
    }

    // 只有后端返回的数字分类 ID 才作为 category_id 发送。
    // “热门”和“最新”是排序频道，不能被 parseInt 后误发成 category_id=NaN。
    const categoryId = Number(activeCategory.value)
    if (Number.isInteger(categoryId) && categoryId > 0) {
      params.category_id = categoryId
      console.log('筛选分类ID:', params.category_id)
    }

    // 推荐和热门按播放量排序，最新保持创建时间倒序。
    if (activeCategory.value === 'recommend' || activeCategory.value === 'popular') {
      params.ordering = '-views_count'
    }

    console.log('请求参数:', params)
    const response = await service.get('/videos/videos/', { params })
    console.log('获取到的视频数量:', response.results?.length || 0)
    
    if (page === 1) {
      videos.value = response.results || []
    } else {
      videos.value = [...videos.value, ...(response.results || [])]
    }
    
    // 为每个视频添加 isHovering 属性
    videos.value = videos.value.map(v => ({
      ...v,
      isHovering: false
    }))

    hasMore.value = !!response.next
    currentPage.value = page
  } catch (error) {
    console.error('获取视频列表失败:', error)
    errorMessage.value = '请检查网络连接后再试。'
    if (page === 1) videos.value = []
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

const handleCategoryChange = (categoryId, index) => {
  activeCategory.value = categoryId
  currentPage.value = 1
  hasMore.value = true
  fetchVideos(1)
  updateIndicator(index)
}

const updateIndicator = (index) => {
  const targetTab = categoryRefs.value[index]
  if (targetTab) {
    const containerRect = categoryContainer.value?.getBoundingClientRect()
    const tabRect = targetTab.getBoundingClientRect()
    
    if (containerRect) {
      const left = tabRect.left - containerRect.left + categoryContainer.value.scrollLeft
      indicatorStyle.value = {
        width: `${tabRect.width}px`,
        transform: `translateX(${left}px)`
      }
    }
  }
}

const loadMore = () => {
  if (!loadingMore.value && hasMore.value) {
    fetchVideos(currentPage.value + 1)
  }
}

const goToVideo = (videoId) => {
  router.push(`/video/${videoId}`)
}

const goToUser = (userId) => {
  router.push(`/user/${userId}`)
}

const goToCreate = () => {
  if (getToken()) {
    router.push('/user/dashboard/create')
    return
  }
  router.push({
    path: '/auth',
    query: { redirect: '/user/dashboard/create' }
  })
}

const retryCurrentView = () => fetchVideos(1)

const formatDuration = (seconds) => {
  if (!seconds && seconds !== 0) return '00:00'
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`
}

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + 'w'
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toString()
}

onMounted(() => {
  fetchCategories()
  fetchVideos(1)
  // 初始化指示器位置
  setTimeout(() => {
    updateIndicator(0)
  }, 100)
})
</script>


<style scoped>
.douyin-home {
  min-height: 100vh;
  background: var(--color-background, #f6f8fb);
  width: 100%;
  overflow-x: hidden;
}

.category-bar {
  position: sticky;
  top: 60px;
  background: var(--color-surface, #fff);
  border-bottom: 1px solid var(--color-border, #e2e8f0);
  z-index: 100;
  padding: 0 20px;
  width: 100%;
  box-sizing: border-box;
}

.category-container {
  width: 100%;
  box-sizing: border-box;
  display: flex;
  gap: 20px;
  overflow-x: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
  padding: 12px 0;
  position: relative;
}

.category-container::-webkit-scrollbar {
  display: none;
}

.category-tab {
  appearance: none;
  border: 0;
  background: transparent;
  padding: 8px 16px;
  min-height: 40px;
  font-size: 14px;
  font-weight: 500;
  color: #61666d;
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--motion-fast, 150ms) ease, background-color var(--motion-fast, 150ms) ease;
  user-select: none;
  position: relative;
  z-index: 1;
}

.category-tab:hover {
  color: var(--color-text, #0f172a);
  background: var(--color-surface-muted, #f1f5f9);
}

.category-tab.active {
  color: var(--color-primary, #2563eb);
  font-weight: 600;
}

.category-indicator {
  position: absolute;
  bottom: 12px;
  left: 0;
  height: calc(100% - 24px);
  background: var(--color-primary-soft, #eff6ff);
  border-radius: 8px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 0;
}

.main-container {
  width: 100%;
  padding: 12px 8px 20px;
  box-sizing: border-box;
  overflow-x: hidden;
}

.video-waterfall {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  margin-bottom: 40px;
  width: 100%;
  box-sizing: border-box;
}

.video-item {
  background: #ffffff;
  cursor: pointer;
  overflow: hidden;
  width: 100%;
  animation: cardFadeIn 0.5s ease-out both;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.video-item:hover {
  transform: translateY(-4px);
}

@keyframes cardFadeIn {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* 第一个视频占据 2x2 */
.video-cover-wrapper {
  border-radius: 10px;
  position: relative;
  width: 100%;
  padding-top: 58.25%; /* 16:9 比例 */
  background: #0f172a;
  overflow: hidden;
}

.video-cover {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.video-cover :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-preview {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-error {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #667eea;
  color: rgba(255, 255, 255, 0.8);
  font-size: 40px;
}

/* 播放时长 - 左下角 */
.video-duration-overlay {
  position: absolute;
  bottom: 8px;
  left: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.7);
  border-radius: 4px;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.3s ease;
}

.video-item:hover .video-duration-overlay {
  background: rgba(59, 130, 246, 0.85);
  transform: scale(1.05);
}

.play-icon-small {
  font-size: 12px;
}

/* 分辨率标识 */
.resolution-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.5px;
}

.resolution-badge[class~="4k"] {
  background: #ff6b6b;
  box-shadow: 0 2px 8px rgba(238, 90, 36, 0.4);
}

.resolution-badge[class~="2k"] {
  background: #a29bfe;
  box-shadow: 0 2px 8px rgba(108, 92, 231, 0.4);
}

.video-info-wrapper {
  padding: 10px 2px 0;
  background: transparent;
  width: 100%;
  font-size: 15px;
  font-weight: 500;
}

.video-title {
  text-align: left;
  color: var(--color-text, #0f172a);
  line-height: 1.4;
  margin: 0 0 8px 0;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: break-word;
  transition: color 0.3s;
}

.video-item:hover .video-title {
  color: #3b82f6;
}

.video-meta-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  font-size: 11px;
  color: #9ca3af;
  gap: 8px;
}

.author-info {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text-secondary, #475569);
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 1;
  min-width: 0;
}

.author-info:hover {
  color: #3b82f6;
  transform: translateX(2px);
}

.author-info .el-avatar {
  transition: transform 0.3s ease;
}

.author-info:hover .el-avatar {
  transform: scale(1.1);
}

.author-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-stats {
  color: var(--color-text-muted, #64748b);
  white-space: nowrap;
  flex-shrink: 0;
}

.load-more-wrapper {
  display: flex;
  justify-content: center;
  padding: 40px 0;
  width: 100%;
}

.load-more-wrapper .el-button {
  padding: 12px 32px;
  font-size: 15px;
  font-weight: 500;
  border-radius: 8px;
  background: #18191c;
  border: none;
  color: #fff;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.load-more-wrapper .el-button::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  transition: width 0.6s, height 0.6s;
}

.load-more-wrapper .el-button:hover::before {
  width: 300px;
  height: 300px;
}

.load-more-wrapper .el-button:hover {
  background: #3b82f6;
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(59, 130, 246, 0.4);
}

.load-more-wrapper .el-button:active {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 100px 0;
  color: #61666d;
  width: 100%;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e3e5e7;
  border-top-color: #18191c;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 100px 0;
  color: var(--color-text-secondary, #475569);
  animation: fadeIn 0.6s ease-out;
  width: 100%;
}

.empty-icon {
  font-size: 80px;
  margin-bottom: 16px;
  opacity: 0.4;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.4;
  }
  50% {
    transform: scale(1.05);
    opacity: 0.6;
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.empty-state p {
  font-size: 15px;
  color: var(--color-text-muted, #64748b);
  font-weight: 400;
  margin: 8px 0 0;
}

.empty-state strong {
  color: var(--color-text, #0f172a);
  font-size: 18px;
}

.empty-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.error-state .empty-icon {
  color: var(--color-danger, #dc2626);
  animation: none;
}

@media (prefers-reduced-motion: reduce) {
  .video-item,
  .empty-state,
  .empty-icon {
    animation: none;
  }
}

@media (max-width: 1400px) {
  .video-waterfall {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (max-width: 1024px) {
  .video-waterfall {
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
}

@media (max-width: 768px) {
  .category-bar {
    padding: 0 12px;
  }
  
  .category-container {
    gap: 20px;
  }
  
  .main-container {
    padding: 12px;
  }
  
  .video-waterfall {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }
}

@media (max-width: 480px) {
  .video-waterfall {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  
  .category-container {
    gap: 16px;
  }
}
</style>
