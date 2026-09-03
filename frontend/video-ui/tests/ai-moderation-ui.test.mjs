import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../src/views/admin/ai/', import.meta.url);

test('cloud moderation UI uses label confidence instead of legacy risk scores', async () => {
  const page = await readFile(new URL('AIModeration.vue', root), 'utf8');
  const detail = await readFile(new URL('components/ModerationDetailDialog.vue', root), 'utf8');

  assert.match(page, /标签匹配置信度/);
  assert.match(detail, /最高标签匹配置信度/);
  assert.doesNotMatch(page, /row\.medium_score|row\.high_score/);
});

test('cloud moderation confirmation does not expose ineffective local parameters', async () => {
  const page = await readFile(new URL('AIModeration.vue', root), 'utf8');
  const confirmation = await readFile(new URL('components/ModerationConfigDialog.vue', root), 'utf8');

  assert.doesNotMatch(page, /moderationConfig|threshold_level|\.\.\./);
  assert.doesNotMatch(confirmation, /el-slider|el-input-number|threshold|fps/);
  assert.match(confirmation, /临时上传到私有 OSS/);
});

test('manual review exposes separate false-positive and violation actions', async () => {
  const detail = await readFile(new URL('components/ModerationDetailDialog.vue', root), 'utf8');
  const stats = await readFile(new URL('components/StatsCards.vue', root), 'utf8');

  assert.match(detail, /确认误报并通过/);
  assert.match(detail, /确认安全并通过/);
  assert.match(detail, /确认违规并拒绝/);
  assert.match(stats, /stats\?\.uncertain/);
  assert.doesNotMatch(stats, /unsafe \|\| 0\) \+ \(stats\?\.uncertain/);
});

test('moderation submission updates rows immediately and follows task completion', async () => {
  const page = await readFile(new URL('AIModeration.vue', root), 'utf8');

  assert.match(page, /markModerationsProcessing\(videoIds\)/);
  assert.match(page, /getAITaskStatus\(taskId\)/);
  assert.match(page, /trackModerationTask\(response\.task_id\)/);
  assert.match(page, /TASK_POLL_INTERVAL = 1500/);
  assert.match(page, /onBeforeUnmount/);
});

test('moderation detail keeps the admin light theme and provides reviewable video evidence', async () => {
  const detail = await readFile(new URL('components/ModerationDetailDialog.vue', root), 'utf8');
  const editorToolbar = await readFile(
    new URL('../../../components/creator/EditorToolbar.vue', root),
    'utf8'
  );

  assert.match(detail, /class="moderation-detail-dialog"/);
  assert.match(detail, /detail\.video\.playback_url/);
  assert.match(detail, /播放此时间段/);
  assert.match(detail, /截图仅用于定位，不能单独证明违规/);
  assert.match(detail, /fit="contain"/);
  assert.match(detail, /moderation-detail-dialog\.el-dialog[\s\S]*background: #fff !important/);
  assert.doesNotMatch(editorToolbar, /body \.el-dialog/);
  assert.doesNotMatch(editorToolbar, /\.el-overlay \.el-dialog__body/);
});
