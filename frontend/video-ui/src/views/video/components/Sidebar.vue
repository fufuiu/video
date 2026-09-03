<template>
  <div class="sidebar-wrapper" :class="{ open: show }" :aria-hidden="!show">
    <div class="comment-panel" v-show="show" role="dialog" aria-label="视频信息与评论" @click.stop>
      <div class="panel-header">
        <div class="panel-tabs" role="tablist" aria-label="侧栏内容">
          <button 
            class="tab-btn" 
            :class="{ active: activeTab === 'user' }" 
            role="tab"
            :aria-selected="activeTab === 'user'"
            @click.stop="$emit('update:activeTab', 'user')"
          >
            作者
          </button>
          <button 
            class="tab-btn" 
            :class="{ active: activeTab === 'comments' }" 
            role="tab"
            :aria-selected="activeTab === 'comments'"
            @click.stop="$emit('update:activeTab', 'comments')"
          >
            评论 {{ commentCount }}
          </button>
        </div>
        <button class="close-btn" aria-label="关闭侧栏" title="关闭（Esc）" @click="$emit('close')">
          <el-icon><Close /></el-icon>
        </button>
      </div>

      <!-- 作者信息 -->
      <UserPanel
        v-if="activeTab === 'user'"
        :creator-name="creatorName"
        :creator-avatar="creatorAvatar"
        :publish-time="publishTime"
        :is-own-video="isOwnVideo"
        :is-subscribed="isSubscribed"
        :videos="authorVideos"
        :loading="authorLoading"
        @toggle-subscribe="$emit('toggle-subscribe')"
        @go-to-user-detail="$emit('go-to-user-detail')"
        @go-to-video="$emit('go-to-video', $event)"
      />

      <!-- 评论 -->
      <CommentPanel
        v-else
        :comments="comments"
        :user-avatar="userAvatar"
        @add-comment="$emit('add-comment', $event)"
        @toggle-comment-like="$emit('toggle-comment-like', $event)"
        @reply-comment="$emit('reply-comment', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { Close } from '@element-plus/icons-vue';
import UserPanel from './UserPanel.vue';
import CommentPanel from './CommentPanel.vue';

defineProps({
  show: Boolean,
  activeTab: String,
  commentCount: [String, Number],
  creatorName: String,
  creatorAvatar: String,
  publishTime: String,
  isOwnVideo: Boolean,
  isSubscribed: Boolean,
  authorVideos: Array,
  authorLoading: Boolean,
  comments: Array,
  userAvatar: String
});

defineEmits([
  'close',
  'update:activeTab',
  'toggle-subscribe',
  'go-to-user-detail',
  'go-to-video',
  'add-comment',
  'toggle-comment-like',
  'reply-comment'
]);
</script>

<style scoped>
.sidebar-wrapper {
  width: 0;
  height: 100%;
  overflow: hidden;
  flex: 0 0 auto;
  transition: width 0.3s ease;
}

.sidebar-wrapper.open {
  width: 460px;
}

.comment-panel {
  position: relative;
  width: 460px;
  height: 100%;
  background: #171922;
  z-index: 1;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 30px rgba(0,0,0,0.5);
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  transform: translateX(100%);
  transition: transform 0.3s ease;
}

.sidebar-wrapper.open .comment-panel {
  transform: translateX(0);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.panel-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-btn {
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid #3b3e49;
  background: #252832;
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: #30333e;
  color: #fff;
}

.tab-btn.active {
  background: #006f94;
  border-color: #21b7e8;
  color: #fff;
}

.close-btn {
  width: 44px;
  height: 44px;
  border: none;
  background: #2b2e38;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.7);
  transition: all 0.2s;
}

.close-btn:hover {
  background: #3a3d48;
  color: #fff;
}

.tab-btn:focus-visible,
.close-btn:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}

@media (max-width: 768px) {
  .sidebar-wrapper {
    position: absolute;
    inset: 0 0 0 auto;
    z-index: 220;
    pointer-events: none;
    transition: none;
  }

  .sidebar-wrapper.open {
    width: 100%;
    pointer-events: auto;
  }
  
  .comment-panel {
    width: 100%;
  }
}
</style>
