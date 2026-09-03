<template>
  <div class="immersive-player-page">
    <div class="main-stage" :class="{ 'sidebar-open': showSidebar }" @wheel="handleWheel">
      <!-- 视频滑动容器 -->
      <VideoSlider
        :prev-video="prevVideo"
        :next-video="nextVideo"
        :slider-style="sliderStyle"
        :is-transitioning="isTransitioning"
      >
        <!-- 视频播放器 -->
        <VideoPlayer
          ref="playerRef"
          :video-id="videoId"
          :hls-url="videoData.hls_file"
          :poster-url="videoData.thumbnail"
          :danmaku-list="danmakuList"
          :subtitle-list="subtitleList"
          :subtitle-style="subtitleStyle"
          :is-clean-mode="isCleanMode"
          :is-loading="loading"
          :error-message="playerError"
          @play="isPaused = false"
          @pause="isPaused = true"
          @danmaku-send="sendDanmaku"
        />
      </VideoSlider>

      <div v-if="loading || playerError" class="player-state" role="status" aria-live="polite">
        <el-icon v-if="loading" class="is-loading" :size="32"><Loading /></el-icon>
        <el-icon v-else :size="32"><WarningFilled /></el-icon>
        <strong>{{ loading ? '正在加载视频' : '视频暂时无法播放' }}</strong>
        <p>{{ loading ? '正在准备播放资源，请稍候。' : playerError }}</p>
        <button v-if="playerError" type="button" class="state-action" @click="retryVideo">重新加载</button>
      </div>

      <!-- 顶部导航栏 -->
      <TopBar
        :is-clean-mode="isCleanMode"
        :is-own-video="isOwnVideo"
        :video-id="videoId"
        @go-back="goBack"
        @report="reportVideo"
        @not-interested="notInterested"
      />

      <!-- 右侧互动栏 -->
      <VideoActions
        :creator-avatar="videoData.creatorAvatar"
        :is-subscribed="isSubscribed"
        :is-own-video="isOwnVideo"
        :is-liked="isLiked"
        :is-disliked="isDisliked"
        :is-collected="isCollected"
        :likes="videoData.likes"
        :comment-count="videoData.commentCount"
        :collect-count="videoData.collectCount"
        :is-clean-mode="isCleanMode"
        :active-panel="showSidebar ? sidebarTab : ''"
        @toggle-user-panel="openSidebar('user')"
        @toggle-subscribe="toggleSubscribe"
        @toggle-like="toggleLike"
        @toggle-dislike="toggleDislike"
        @toggle-comment-panel="openSidebar('comments')"
        @toggle-collect="toggleCollect"
        @share="shareVideo"
      />

      <!-- 左下角视频信息 -->
      <VideoInfo
        :video-data="videoData"
        :is-paused="isPaused"
        :is-clean-mode="isCleanMode"
        @ai-summarize="aiSummarize"
        @ai-recognize="aiRecognizeFrame"
      />
    </div>

    <!-- 右侧侧边栏 -->
    <Sidebar
      :show="showSidebar"
      :active-tab="sidebarTab"
      :comment-count="videoData.commentCount"
      :creator-name="videoData.creatorName"
      :creator-avatar="videoData.creatorAvatar"
      :publish-time="videoData.publishTime"
      :is-own-video="isOwnVideo"
      :is-subscribed="isSubscribed"
      :author-videos="authorVideos"
      :author-loading="authorLoading"
      :comments="comments"
      :user-avatar="userAvatar"
      @close="showSidebar = false"
      @update:active-tab="sidebarTab = $event"
      @toggle-subscribe="toggleSubscribe"
      @go-to-user-detail="goToUserDetail"
      @go-to-video="goToVideo"
      @add-comment="handleAddComment"
      @toggle-comment-like="toggleCommentLike"
      @reply-comment="replyToComment"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useUserStore } from '@/store/user';
import { ElMessage } from 'element-plus';
import { Loading, WarningFilled } from '@element-plus/icons-vue';
import service from '@/api/user';

// 组件导入
import TopBar from './components/TopBar.vue';
import VideoPlayer from './components/VideoPlayer.vue';
import VideoActions from './components/VideoActions.vue';
import VideoInfo from './components/VideoInfo.vue';
import Sidebar from './components/Sidebar.vue';
import VideoSlider from './components/VideoSlider.vue';

// Composables
import { useVideoDetail } from './composables/useVideoDetail';
import { useSubtitles } from './composables/useSubtitles';
import { useComments, useDanmaku } from './composables/useComments';
import { useVideoSlider } from './composables/useVideoSlider';

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const videoId = ref(route.params.id);

// 使用 composables
const {
  videoData,
  isOwnVideo,
  isSubscribed,
  isLiked,
  isDisliked,
  isCollected,
  loading,
  fetchVideoDetail,
  recordView,
  toggleSubscribe,
  toggleLike,
  toggleDislike,
  toggleCollect,
  shareVideo,
  formatNumber,
  formatDate,
  formatTimeAgo
} = useVideoDetail(videoId);

const { subtitleList, subtitleStyle, fetchSubtitles } = useSubtitles(videoId);
const { comments, fetchComments, addComment, toggleCommentLike } = useComments(videoId, formatTimeAgo);
const { danmakuList, fetchDanmaku, sendDanmaku } = useDanmaku(videoId);
const {
  videoList,
  prevVideo,
  nextVideo,
  sliderStyle,
  isTransitioning,
  fetchVideoList,
  handleWheel: handleVideoWheel
} = useVideoSlider(videoId);

// 本地状态
const playerRef = ref(null);
const isPaused = ref(true);
const isCleanMode = ref(false);
const showSidebar = ref(false);
const sidebarTab = ref('user');
const authorVideos = ref([]);
const authorLoading = ref(false);
const playerError = ref('');

const userAvatar = computed(() => userStore.userInfo?.avatar || '');

// 侧边栏操作
const openSidebar = (tab) => {
  if (showSidebar.value && sidebarTab.value === tab) {
    showSidebar.value = false;
    return;
  }
  sidebarTab.value = tab;
  showSidebar.value = true;
  if (tab === 'user' && authorVideos.value.length === 0) {
    fetchAuthorVideos();
  }
};

const handleGlobalKeydown = (event) => {
  if (event.key === 'Escape' && showSidebar.value) {
    showSidebar.value = false;
  }
};

// 获取作者视频
const fetchAuthorVideos = async () => {
  if (!videoData.value.creatorId || authorLoading.value) return;
  authorLoading.value = true;
  try {
    const response = await service({
      url: '/videos/videos/',
      method: 'get',
      params: { user_id: videoData.value.creatorId, page_size: 30 }
    });
    authorVideos.value = response.results || response || [];
  } catch (error) {
    console.error('获取作者视频失败:', error);
    authorVideos.value = [];
  } finally {
    authorLoading.value = false;
  }
};

// 导航操作
const goBack = () => router.back();
const goToVideo = (id) => { if (id) router.push(`/video/${id}`); };
const goToUserDetail = () => {
  if (!videoData.value.creatorId) return;
  router.push(`/user/${videoData.value.creatorId}`);
};

// 举报和不感兴趣
const reportVideo = () => {
  // 举报成功的提示已在 ReportDialog 中处理
};
const notInterested = () => ElMessage.success('已标记为不感兴趣');

// AI 功能
const aiSummarize = () => ElMessage.info('AI正在分析视频内容...');
const aiRecognizeFrame = () => ElMessage.info('AI正在识别当前画面...');

// 评论操作
const handleAddComment = async (text) => {
  const success = await addComment(text);
  if (success) {
    videoData.value.commentCount += 1;
  }
};

const replyToComment = (comment) => {
  ElMessage.info(`回复 @${comment.username}`);
};

// 滚轮切换视频
const handleWheel = (e) => {
  handleVideoWheel(e, async (targetVideo, preloadedData) => {
    // 先更新数据再切换路由，减少闪烁
    videoData.value = {
      id: preloadedData.id,
      title: preloadedData.title,
      description: preloadedData.description || '',
      views: formatNumber(preloadedData.views_count),
      likes: formatNumber(preloadedData.likes_count),
      commentCount: preloadedData.comments_count || 0,
      collectCount: preloadedData.favorites_count || 0,
      publishTime: formatDate(preloadedData.published_at || preloadedData.created_at),
      creatorName: preloadedData.user?.username || '未知用户',
      creatorId: preloadedData.user?.id,
      creatorAvatar: preloadedData.user?.avatar || '',
      category: preloadedData.category,
      tags: preloadedData.tags || [],
      hls_file: preloadedData.hls_file,
      thumbnail: preloadedData.thumbnail
    };
    
    // 重置作者视频
    authorVideos.value = [];
    
    // 更新状态
    isLiked.value = preloadedData.is_liked || false;
    isCollected.value = preloadedData.is_favorited || false;
    videoId.value = targetVideo.id;
    
    // 重新初始化播放器
    if (playerRef.value) {
      playerRef.value.destroy();
    }
    
    // 重新加载数据
    await fetchDanmaku();
    await fetchSubtitles();
    fetchComments();
    recordView();
    
    // 如果侧边栏打开且在作者tab，重新加载作者视频
    if (showSidebar.value && sidebarTab.value === 'user') {
      fetchAuthorVideos();
    }
  });
};

// 初始化
onMounted(async () => {
  window.addEventListener('keydown', handleGlobalKeydown);
  try {
    await fetchDanmaku();
    await fetchSubtitles();
    await fetchVideoDetail();
    if (!videoData.value.hls_file) {
      playerError.value = '暂时没有可用的播放资源，请稍后再试。';
    }
    fetchComments();
    recordView();
    fetchVideoList();
  } catch (error) {
    playerError.value = '视频信息加载失败，请检查网络后重试。';
  }
});

const retryVideo = async () => {
  playerError.value = '';
  try {
    await fetchVideoDetail();
    if (!videoData.value.hls_file) {
      playerError.value = '暂时没有可用的播放资源，请稍后再试。';
    }
  } catch (error) {
    playerError.value = '视频信息加载失败，请检查网络后重试。';
  }
};

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown);
  if (playerRef.value) {
    playerRef.value.destroy();
  }
});
</script>

<style scoped>
.immersive-player-page {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: #000;
  overflow: hidden;
  display: flex;
  flex-direction: row;
}

.main-stage {
  position: relative;
  flex: 1;
  height: 100%;
  min-width: 0;
  overflow: hidden;
}

.player-state {
  position: absolute;
  inset: 50% auto auto 50%;
  z-index: 240;
  width: min(360px, calc(100% - 40px));
  padding: 28px 24px;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-align: center;
  color: #fff;
  background: rgba(23, 25, 34, 0.94);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 16px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
}

.player-state .el-icon {
  color: #fb7299;
}

.player-state strong {
  font-size: 18px;
}

.player-state p {
  margin: 0;
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  line-height: 1.6;
}

.state-action {
  min-height: 44px;
  margin-top: 6px;
  padding: 0 18px;
  border: 0;
  border-radius: 999px;
  color: #fff;
  background: #fb7299;
  cursor: pointer;
}

@media (max-width: 768px) {
  .immersive-player-page {
    display: block;
  }
  
  .main-stage {
    width: 100%;
    height: 100%;
  }
}
</style>
