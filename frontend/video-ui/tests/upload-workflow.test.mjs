import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';


test('subtitle editor clears previous video state before loading another video', async () => {
  const source = await readFile(
    new URL('../src/views/creator/SubtitleEditor.vue', import.meta.url),
    'utf8'
  );

  assert.match(source, /const resetEditorState = \(\) =>/);
  assert.match(source, /videoUrl\.value = ''/);
  assert.match(source, /subtitles\.value = \[\]/);
  assert.match(source, /resetEditorState\(\)[\s\S]*Promise\.all\(\[loadVideoInfo\(\), loadSubtitles\(\)\]\)/);
  assert.match(source, /isEditBeforeTranscode\.value && !videoId/);
  assert.match(source, /videoStatus\.value === 'pending_subtitle_edit'/);
  assert.match(source, /完成字幕并开始处理/);
});


test('creation workflow saves metadata before handing off subtitle processing', async () => {
  const source = await readFile(
    new URL('../src/views/dashboard/CreateCenter.vue', import.meta.url),
    'utf8'
  );
  const submitWorkflow = source.slice(
    source.indexOf('const submitVideo = async () =>'),
    source.indexOf('// ==================== 字幕编辑引导功能 ====================')
  );

  assert.match(submitWorkflow, /throw new Error\('视频文件已上传，但作品信息保存失败/);
  assert.match(submitWorkflow, /视频和作品信息已保存，请选择字幕处理方式/);
  assert.doesNotMatch(submitWorkflow, /await publishVideo\(videoId\)/);
  assert.match(submitWorkflow, /handleSubtitleDetectionResult\(videoId, subtitleInfoForNextStep\)/);
  assert.match(source, /query: \{ videoId, mode: 'edit_before_transcode' \}/);
});


test('subtitle editor renders a time-synchronized video preview overlay', async () => {
  const source = await readFile(
    new URL('../src/components/creator/VideoPlayerSection.vue', import.meta.url),
    'utf8'
  );

  assert.match(source, /class="subtitle-preview-overlay"/);
  assert.match(source, /const currentPreviewSubtitle = computed/);
  assert.match(source, /time >= start && time < end/);
  assert.match(source, /playerCurrentTime\.value = Number\(artplayer\.value\?\.currentTime\) \|\| 0/);
  assert.match(source, /Math\.max\(0\.75, Math\.min\(1, containerWidth \/ 640\)\)/);
  assert.match(source, /\.video-container :deep\(\.art-subtitle\)[\s\S]*display: none !important/);
});


test('subtitle display tabs switch main and translated text in list and preview', async () => {
  const [editor, player, list] = await Promise.all([
    readFile(new URL('../src/views/creator/SubtitleEditor.vue', import.meta.url), 'utf8'),
    readFile(new URL('../src/components/creator/VideoPlayerSection.vue', import.meta.url), 'utf8'),
    readFile(new URL('../src/components/creator/SubtitleList.vue', import.meta.url), 'utf8')
  ]);

  assert.match(editor, /const subtitleDisplayMode = ref\('both'\)/);
  assert.match(editor, /@update:display-mode="subtitleDisplayMode = \$event"/);
  assert.match(list, /@click="setDisplayMode\('main'\)"/);
  assert.match(list, /@click="setDisplayMode\('translation'\)"/);
  assert.match(list, /v-if="displayMode !== 'translation'"/);
  assert.match(list, /v-if="displayMode !== 'main'"/);
  assert.match(player, /subtitleDisplayMode !== 'translation' && currentPreviewSubtitle\.text/);
  assert.match(player, /subtitleDisplayMode !== 'main' && currentPreviewSubtitle\.translation/);
});
