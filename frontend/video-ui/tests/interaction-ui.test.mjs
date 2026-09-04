import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(`../src/${path}`, import.meta.url), 'utf8');

const collectUiFiles = async (directory) => {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map((entry) => {
    const url = new URL(`${entry.name}${entry.isDirectory() ? '/' : ''}`, directory);
    if (entry.isDirectory()) return collectUiFiles(url);
    return /\.(vue|css|scss)$/.test(entry.name) ? [url] : [];
  }));
  return nested.flat();
};

test('video page keeps wheel navigation outside the comment drawer', async () => {
  const source = await read('views/video/detail-refactored.vue');

  assert.match(source, /class="main-stage"[^>]*@wheel="handleWheel"/);
  assert.doesNotMatch(source, /class="immersive-player-page"[^>]*@wheel/);
  assert.match(source, /event\.key === 'Escape'/);
});

test('video actions are keyboard-operable buttons with visible state', async () => {
  const source = await read('views/video/components/VideoActions.vue');

  assert.match(source, /<button type="button" class="action-item"/);
  assert.match(source, /:aria-pressed="activePanel === 'comments'"/);
  assert.match(source, /aria-label="打开评论"/);
  assert.match(source, /\.action-item:focus-visible/);
});

test('core player controls do not use backdrop blur', async () => {
  const componentFiles = [
    'CommentPanel.vue',
    'Sidebar.vue',
    'TopBar.vue',
    'VideoActions.vue',
    'VideoInfo.vue',
    'VideoPlayer.vue'
  ];

  for (const file of componentFiles) {
    const source = await read(`views/video/components/${file}`);
    assert.doesNotMatch(source, /backdrop-filter|filter:\s*blur/, `${file} should use solid, readable controls`);
  }
});

test('manual review actions prevent duplicate submissions', async () => {
  const source = await read('views/admin/videos/ReviewVideos.vue');

  assert.match(source, /:loading="actionLoading\[row\.id\] === 'approve'"/);
  assert.match(source, /:loading="reviewActionLoading"/);
  assert.match(source, /if \(processingLoading\.value\) return/);
});

test('creator workshop compact controls use native button semantics', async () => {
  const player = await read('components/creator/VideoPlayerSection.vue');
  const createCenter = await read('views/dashboard/CreateCenter.vue');

  assert.match(player, /<button type="button" class="select-option"/);
  assert.match(player, /<button type="button" role="tab" class="tab-btn"/);
  assert.match(player, /<button type="button" class="collapse-icon-bar"/);
  assert.doesNotMatch(player, /<div class="select-option"[^>]*@click/);
  assert.match(createCenter, /<div class="logo/);
  assert.doesNotMatch(createCenter, /class="logo[^>]*@click/);
  assert.match(createCenter, /返回工作台/);
  assert.doesNotMatch(createCenter, /\.record-btn:hover\s*\{[^}]*animation:/s);
  assert.match(createCenter, /<button type="button" class="tag-remove/);
});

test('entry pages expose explicit back navigation', async () => {
  const auth = await read('components/user/AuthForm.vue');
  const userCenter = await read('layout/user/UserCenter.vue');

  assert.match(auth, /class="auth-back-btn"[^>]*@click="goHome"/);
  assert.match(auth, /const goHome = \(\) => router\.push\('\/home'\)/);
  assert.match(userCenter, /class="nav-back-btn"[^>]*@click="goHome"/);
  assert.match(userCenter, />返回首页</);
});

test('protected creator navigation keeps token and user store in sync', async () => {
  const router = await read('router/index.js');
  const auth = await read('components/user/AuthForm.vue');
  const home = await read('views/home/index.vue');

  assert.match(router, /const userStore = useUserStore\(\)/);
  assert.match(router, /const hasToken = Boolean\(getToken\(\)\)/);
  assert.match(router, /query: \{ redirect: to\.fullPath \}/);
  assert.match(auth, /let userInfo = res\.user/);
  assert.doesNotMatch(auth, /loginAction\(\{ username: loginForm\.username \}\)/);
  assert.match(home, /if \(getToken\(\)\) \{[\s\S]*\/user\/dashboard\/create/);
});

test('login form exposes validation rules used by its template', async () => {
  const auth = await read('components/user/AuthForm.vue');

  assert.match(auth, /const loginRules = \{/);
  assert.match(auth, /:rules="loginRules"/);
  assert.match(auth, /username: \[[\s\S]*请输入用户名或邮箱/);
  assert.match(auth, /password: \[[\s\S]*请输入密码/);
});

test('home sort channels do not send string channel ids as category filters', async () => {
  const home = await read('views/home/index.vue');

  assert.match(home, /Number\.isInteger\(categoryId\) && categoryId > 0/);
  assert.doesNotMatch(home, /params\.category_id = parseInt\(activeCategory\.value\)/);
  assert.match(home, /activeCategory\.value === 'recommend' \|\| activeCategory\.value === 'popular'/);
});

test('profile username is a read-only login identifier', async () => {
  const profile = await read('views/user/ProfileView.vue');

  assert.match(profile, /v-model="userData\.username"[\s\S]*?readonly/);
  assert.match(profile, /用户名是登录标识，注册后不可修改/);
  assert.doesNotMatch(profile, /updateData\.username/);
});

test('profile nickname is used for the signed-in display name', async () => {
  const profile = await read('views/user/ProfileView.vue');
  const store = await read('store/user.js');
  const topNav = await read('components/common/TopNav.vue');

  assert.match(profile, /userData\.last_name \|\| userData\.username/);
  assert.match(profile, /const updatedUser = await updateUserProfile\(updateData\)/);
  assert.match(profile, /userStore\.updateUserInfo\(updatedUser\)/);
  assert.match(store, /displayName: \(state\) => state\.userInfo\?\.display_name\?\.trim\(\) \|\| state\.userInfo\?\.last_name\?\.trim\(\) \|\| state\.username/);
  assert.match(topNav, /userStore\.displayName/);
});

test('published subtitle playback can read saved data and preserves zero timestamps', async () => {
  const subtitles = await read('views/video/composables/useSubtitles.js');
  const detail = await read('views/video/detail-refactored.vue');

  assert.match(subtitles, /getVideoSubtitles\(videoId\.value\)/);
  assert.match(subtitles, /sub\.startTime \?\? sub\.start_time/);
  assert.match(detail, /await fetchSubtitles\(\)/);
});

test('creator workshop uses the existing SVG icon library instead of emoji icons', async () => {
  const player = await read('components/creator/VideoPlayerSection.vue');

  assert.match(player, /FolderOpened/);
  assert.match(player, /Cloudy/);
  assert.match(player, /Brush/);
  assert.match(player, /Scissor/);
  assert.doesNotMatch(player, /📁|☁️|🎨|✂️|📤|📥|▲|▼/);
});

test('production UI uses solid surfaces instead of gradients or backdrop blur', async () => {
  const files = await collectUiFiles(new URL('../src/', import.meta.url));

  for (const file of files) {
    const source = await readFile(file, 'utf8');
    assert.doesNotMatch(
      source,
      /(?:linear|radial|conic)-gradient|graphic\.LinearGradient|backdrop-filter|filter:\s*blur/i,
      `${file.pathname} should use solid color, border, and spacing for hierarchy`
    );
  }
});
