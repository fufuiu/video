"""
Whisper 模型评估工具 (无监督评估)
评估 faster-whisper 的性能和输出分布
"""
import os
import time
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from pathlib import Path
from collections import Counter
import json
import tempfile
import subprocess
import sys

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 添加当前目录到 sys.path
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    import sys
    sys.path.append(str(current_dir))

class WhisperEvaluator:
    """Whisper 模型评估工具 (无监督评估)"""

    def __init__(self, model_path: str = None):
        """
        Args:
            model_path: Whisper 模型路径，默认使用 E:/Web/video_web/backend/video/video/models/whisper-ct2-large-v3
        """
        self.model_path = model_path
        self.model = None
        self.device = None
        self.compute_type = None
        self.results = {}

    def _load_model(self):
        """加载 Whisper 模型"""
        if self.model is not None:
            return self.model
        
        try:
            import torch
            from faster_whisper import WhisperModel
        except ImportError as e:
            print(f"Whisper 依赖不可用: {e}")
            return None
        
        # 模型路径
        if self.model_path:
            model_dir = Path(self.model_path)
        else:
            model_dir = Path("E:/Web/video_web/backend/video/video/models/whisper-ct2-large-v3")
        
        if not model_dir.exists():
            print(f"Whisper 模型不存在: {model_dir}")
            return None
        
        # 确定设备和计算类型
        if torch.cuda.is_available():
            self.device = 'cuda'
            self.compute_type = 'int8_float16'
            print("使用 CUDA 加速")
        else:
            self.device = 'cpu'
            self.compute_type = 'int8'
            print("使用 CPU 推理")
        
        print(f"加载 Whisper 模型: {model_dir}")
        self.model = WhisperModel(
            str(model_dir),
            device=self.device,
            compute_type=self.compute_type,
            num_workers=4
        )
        print("Whisper 模型加载完成")
        
        return self.model

    def _extract_audio(self, video_path, output_path):
        """从视频中提取音频"""
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-map', '0:a:0', '-vn',
            '-ac', '1', '-ar', '16000',
            '-acodec', 'pcm_s16le',
            '-af', 'aresample=16000:resampler=soxr:precision=28,volume=0.95',
            '-y', str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode != 0:
            print(f"音频提取失败: {result.stderr}")
            return False
        return True

    def _transcribe(self, audio_path, language='auto'):
        """转录音频"""
        model = self._load_model()
        if not model:
            return None
        
        lang_arg = None if language in (None, '', 'auto') else language
        
        params = {
            'language': lang_arg,
            'task': 'transcribe',
            'beam_size': 20,
            'temperature': 0.0,
            'condition_on_previous_text': True,
            'compression_ratio_threshold': 2.0,
            'log_prob_threshold': -0.8,
            'no_speech_threshold': 0.6,
            'vad_filter': False,
            'word_timestamps': False,
        }
        
        segments, info = model.transcribe(str(audio_path), **params)
        
        subtitles = []
        for seg in segments:
            subtitle = {
                'startTime': float(seg.start or 0),
                'endTime': float(seg.end or 0),
                'text': (seg.text or '').strip(),
            }
            if subtitle['text']:
                subtitles.append(subtitle)
        
        
        return {
            'subtitles': subtitles,
            'language': getattr(info, 'language', '') or '',
            'count': len(subtitles)
        }

    def release_model(self):
        """释放模型内存"""
        if self.model is not None:
            del self.model
            self.model = None
            
            import gc
            gc.collect()
            
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    print("已清理 CUDA 缓存")
            except ImportError:
                pass
            
            print("Whisper 模型已释放")

    def evaluate_audio_files(self, folder_path: str, limit: int = 100, 
                             language: str = 'auto'):
        """
        评估文件夹中的音频文件
        
        Args:
            folder_path: 音频文件夹路径
            limit: 最大评估文件数
            language: 语言代码 ('auto' 自动检测)
            
        Returns:
            评估结果字典
        """
        import glob
        
        print(f"正在评估音频文件夹: {folder_path}")
        
        # 获取音频文件列表
        extensions = ('*.wav', '*.mp3', '*.m4a', '*.flac', '*.ogg', '*.aac')
        files = []
        for ext in extensions:
            files.extend(glob.glob(os.path.join(folder_path, ext)))
            files.extend(glob.glob(os.path.join(folder_path, '**', ext), recursive=True))
        
        files = list(set(files))[:limit]
        print(f"找到 {len(files)} 个音频文件")
        
        if not files:
            print("未找到音频文件")
            return None
        
        results = {
            'file_paths': [],
            'audio_durations': [],
            'process_times': [],
            'real_time_factors': [],  # 处理时间 / 音频时长
            'subtitle_counts': [],
            'total_chars': [],
            'detected_languages': [],
            'avg_segment_durations': [],
            'all_texts': [],
            'text_lengths': [],
            'segment_durations': [],
            'segment_gaps': [],  # 字幕间隔
            'language_confidences': [],
        }
        
        for audio_path in tqdm(files, desc="Processing audio"):
            try:
                # 获取音频时长
                duration = self._get_audio_duration(audio_path)
                if duration <= 0:
                    print(f"无法获取音频时长: {audio_path}")
                    continue
                
                # 提取字幕
                start_time = time.time()
                result = self._transcribe(audio_path, language=language)
                process_time = time.time() - start_time
                
                subtitles = result.get('subtitles', [])
                detected_lang = result.get('language', 'unknown')
                
                # 计算指标
                total_chars = sum(len(sub.get('text', '')) for sub in subtitles)
                segment_durations = []
                segment_gaps = []
                prev_end = 0
                
                for sub in subtitles:
                    start = sub.get('startTime', 0)
                    end = sub.get('endTime', 0)
                    text = sub.get('text', '')
                    
                    duration_seg = end - start
                    segment_durations.append(duration_seg)
                    
                    if prev_end > 0:
                        gap = start - prev_end
                        if gap > 0:
                            segment_gaps.append(gap)
                    
                    prev_end = end
                    
                    if text:
                        results['all_texts'].append(text)
                        results['text_lengths'].append(len(text))
                
                results['file_paths'].append(audio_path)
                results['audio_durations'].append(duration)
                results['process_times'].append(process_time)
                results['real_time_factors'].append(process_time / duration if duration > 0 else 0)
                results['subtitle_counts'].append(len(subtitles))
                results['total_chars'].append(total_chars)
                results['detected_languages'].append(detected_lang)
                results['segment_durations'].extend(segment_durations)
                results['segment_gaps'].extend(segment_gaps)
                
                if segment_durations:
                    results['avg_segment_durations'].append(np.mean(segment_durations))
                else:
                    results['avg_segment_durations'].append(0)
                
            except Exception as e:
                print(f"处理失败 {audio_path}: {e}")
                continue
        
        # 释放模型
        self.release_model()
        
        self.results = results
        return results

    def evaluate_video_files(self, folder_path: str, limit: int = 50, 
                             language: str = 'auto'):
        """
        评估文件夹中的视频文件
        
        Args:
            folder_path: 视频文件夹路径
            limit: 最大评估文件数
            language: 语言代码
            
        Returns:
            评估结果字典
        """
        import glob
        
        print(f"正在评估视频文件夹: {folder_path}")
        
        # 获取视频文件列表
        extensions = ('*.mp4', '*.mkv', '*.avi', '*.mov', '*.webm', '*.flv')
        files = []
        for ext in extensions:
            files.extend(glob.glob(os.path.join(folder_path, ext)))
            files.extend(glob.glob(os.path.join(folder_path, '**', ext), recursive=True))
        
        files = list(set(files))[:limit]
        print(f"找到 {len(files)} 个视频文件")
        
        if not files:
            print("未找到视频文件")
            return None
        
        results = {
            'file_paths': [],
            'video_durations': [],
            'audio_extract_times': [],
            'transcribe_times': [],
            'total_process_times': [],
            'real_time_factors': [],
            'subtitle_counts': [],
            'total_chars': [],
            'detected_languages': [],
            'all_texts': [],
            'text_lengths': [],
            'segment_durations': [],
            'chars_per_second': [],  # 语速
        }
        
        tmp_dir = Path(tempfile.mkdtemp())
        
        try:
            for video_path in tqdm(files, desc="Processing video"):
                try:
                    # 获取视频时长
                    duration = self._get_video_duration(video_path)
                    if duration <= 0:
                        print(f"无法获取视频时长: {video_path}")
                        continue
                    
                    # 提取音频
                    audio_path = tmp_dir / f"audio_{len(results['file_paths'])}.wav"
                    audio_start = time.time()
                    self._extract_audio(video_path, audio_path)
                    audio_time = time.time() - audio_start
                    
                    # 转录
                    transcribe_start = time.time()
                    result = self._transcribe(str(audio_path), language=language)
                    transcribe_time = time.time() - transcribe_start
                    
                    total_time = audio_time + transcribe_time
                    
                    subtitles = result.get('subtitles', [])
                    detected_lang = result.get('language', 'unknown')
                    
                    # 计算指标
                    total_chars = sum(len(sub.get('text', '')) for sub in subtitles)
                    segment_durations = []
                    
                    for sub in subtitles:
                        start = sub.get('startTime', 0)
                        end = sub.get('endTime', 0)
                        text = sub.get('text', '')
                        
                        seg_duration = end - start
                        segment_durations.append(seg_duration)
                        
                        if text:
                            results['all_texts'].append(text)
                            results['text_lengths'].append(len(text))
                            
                            # 计算语速 (字符/秒)
                            if seg_duration > 0:
                                results['chars_per_second'].append(len(text) / seg_duration)
                    
                    results['file_paths'].append(video_path)
                    results['video_durations'].append(duration)
                    results['audio_extract_times'].append(audio_time)
                    results['transcribe_times'].append(transcribe_time)
                    results['total_process_times'].append(total_time)
                    results['real_time_factors'].append(total_time / duration if duration > 0 else 0)
                    results['subtitle_counts'].append(len(subtitles))
                    results['total_chars'].append(total_chars)
                    results['detected_languages'].append(detected_lang)
                    results['segment_durations'].extend(segment_durations)
                    
                    # 清理临时音频
                    if audio_path.exists():
                        audio_path.unlink()
                    
                except Exception as e:
                    print(f"处理失败 {video_path}: {e}")
                    continue
        
        finally:
            # 清理临时目录
            import shutil
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)
            
            # 释放模型
            self.release_model()
        
        self.results = results
        return results

    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                   '-of', 'json', audio_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return float(data.get('format', {}).get('duration', 0))
        except Exception as e:
            print(f"获取音频时长失败: {e}")
        return 0

    def _get_video_duration(self, video_path: str) -> float:
        """获取视频时长"""
        return self._get_audio_duration(video_path)

    def plot_results(self, output_dir: str = "whisper_evaluation_results"):
        """生成学术级评估图表 (精选 3 张代表性图)"""
        if not self.results:
            print("没有评估结果")
            return
        
        from scipy import stats as scipy_stats
        
        os.makedirs(output_dir, exist_ok=True)

        # ══════════════════════════════════════════════════════════════
        # Figure 1: 性能总览 — RTF CDF + 时长vs处理时间回归
        # ══════════════════════════════════════════════════════════════
        durations_key = 'audio_durations' if 'audio_durations' in self.results else 'video_durations'
        times_key = 'process_times' if 'process_times' in self.results else 'total_process_times'
        rtfs_raw = [x for x in self.results.get('real_time_factors', []) if x > 0]

        if rtfs_raw and self.results.get(durations_key):
            rtfs = np.array(rtfs_raw)
            dur = np.array(self.results[durations_key])
            proc = np.array(self.results[times_key])

            fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(14, 5.5))

            # (a) RTF CDF
            sorted_r = np.sort(rtfs)
            cdf = np.arange(1, len(sorted_r) + 1) / len(sorted_r)
            ax0.fill_between(sorted_r, 0, cdf, alpha=0.15, color='steelblue')
            ax0.plot(sorted_r, cdf, color='steelblue', lw=2.2)
            ax0.axvline(1.0, color='#27AE60', ls='-', lw=1.8, label='实时线 (1.0x)')
            for pct, ls in [(50, ':'), (95, '--')]:
                val = np.percentile(rtfs, pct)
                ax0.axvline(val, color='#E74C3C', ls=ls, lw=1.4,
                            label=f'P{pct}: {val:.3f}x')
            ax0.set_xlabel('实时因子 (RTF)', fontsize=11)
            ax0.set_ylabel('累积概率', fontsize=11)
            ax0.set_title('(a) 实时因子累积分布', fontsize=12, fontweight='bold')
            ax0.legend(fontsize=9, framealpha=0.9)
            ax0.grid(alpha=0.25)
            ax0.set_ylim(0, 1.02)

            # (b) 处理时间 vs 媒体时长 回归
            scatter = ax1.scatter(dur, proc, c=rtfs, cmap='RdYlGn_r',
                                  alpha=0.7, s=50, edgecolors='white', lw=0.5,
                                  vmin=0, vmax=max(1.0, np.percentile(rtfs, 90)))
            plt.colorbar(scatter, ax=ax1, label='RTF', shrink=0.85)
            lim = max(dur.max(), proc.max()) * 1.05
            ax1.plot([0, lim], [0, lim], color='#27AE60', ls=':', lw=1.5, alpha=0.6)
            if len(dur) > 2 and np.std(dur) > 0:
                z = np.polyfit(dur, proc, 1)
                p = np.poly1d(z)
                x_line = np.linspace(dur.min(), dur.max(), 100)
                ax1.plot(x_line, p(x_line), color='#E74C3C', ls='--', lw=2)
                r_val, p_val = scipy_stats.pearsonr(dur, proc)
                ax1.text(0.05, 0.95, f'r = {r_val:.3f}\nslope = {z[0]:.3f}',
                         transform=ax1.transAxes, fontsize=10, va='top',
                         bbox=dict(boxstyle='round,pad=0.3',
                                   facecolor='white', alpha=0.85))
            ax1.set_xlabel('媒体时长 (秒)', fontsize=11)
            ax1.set_ylabel('处理时间 (秒)', fontsize=11)
            ax1.set_title('(b) 处理时间 vs 媒体时长', fontsize=12, fontweight='bold')
            ax1.grid(alpha=0.25)

            fig.suptitle('Faster-Whisper 性能评估总览', fontsize=14, fontweight='bold', y=1.02)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, '1_performance_overview.png'),
                        dpi=300, bbox_inches='tight')
            plt.close()

        # ══════════════════════════════════════════════════════════════
        # Figure 2: 转录质量 — 片段时长 Violin + 语速 Violin
        # ══════════════════════════════════════════════════════════════
        has_seg = bool(self.results.get('segment_durations'))
        has_speed = bool(self.results.get('chars_per_second'))
        if has_seg or has_speed:
            ncols = has_seg + has_speed
            fig, axes = plt.subplots(1, ncols, figsize=(7 * ncols, 5.5))
            if ncols == 1:
                axes = [axes]
            ax_i = 0

            if has_seg:
                seg_dur = np.array([d for d in self.results['segment_durations'] if 0 < d < 30])
                if len(seg_dur) > 0:
                    parts = axes[ax_i].violinplot(seg_dur, positions=[0],
                                                   showmeans=True, showmedians=True,
                                                   showextrema=False)
                    for pc in parts['bodies']:
                        pc.set_facecolor('#F39C12')
                        pc.set_alpha(0.35)
                    parts['cmeans'].set_color('#E74C3C')
                    parts['cmedians'].set_color('#2C3E50')
                    np.random.seed(42)
                    sample = np.random.choice(len(seg_dur), min(400, len(seg_dur)), replace=False)
                    jitter = np.random.normal(0, 0.015, len(seg_dur))
                    axes[ax_i].scatter(jitter[sample], seg_dur[sample],
                                       alpha=0.2, s=6, color='#E67E22', zorder=2)
                    axes[ax_i].set_ylabel('片段时长 (秒)', fontsize=11)
                    sub_label = '(a) ' if ncols > 1 else ''
                    axes[ax_i].set_title(f'{sub_label}字幕片段时长分布', fontsize=12, fontweight='bold')
                    axes[ax_i].set_xticks([0])
                    axes[ax_i].set_xticklabels(['Whisper large-v3'])
                    axes[ax_i].grid(axis='y', alpha=0.25)
                    med = np.median(seg_dur)
                    axes[ax_i].axhline(med, ls=':', color='#2C3E50', alpha=0.4)
                    axes[ax_i].text(0.35, med, f'中位数: {med:.2f}s', fontsize=9, va='bottom')
                ax_i += 1

            if has_speed:
                speeds = np.array([s for s in self.results['chars_per_second'] if 0 < s < 50])
                if len(speeds) > 0:
                    parts = axes[ax_i].violinplot(speeds, positions=[0],
                                                   showmeans=True, showmedians=True,
                                                   showextrema=False)
                    for pc in parts['bodies']:
                        pc.set_facecolor('#2ECC71')
                        pc.set_alpha(0.35)
                    parts['cmeans'].set_color('#E74C3C')
                    parts['cmedians'].set_color('#2C3E50')
                    np.random.seed(42)
                    sample = np.random.choice(len(speeds), min(400, len(speeds)), replace=False)
                    jitter = np.random.normal(0, 0.015, len(speeds))
                    axes[ax_i].scatter(jitter[sample], speeds[sample],
                                       alpha=0.2, s=6, color='#27AE60', zorder=2)
                    axes[ax_i].set_ylabel('语速 (字符/秒)', fontsize=11)
                    sub_label = '(b) ' if ncols > 1 else '(a) '
                    axes[ax_i].set_title(f'{sub_label}语速分布', fontsize=12, fontweight='bold')
                    axes[ax_i].set_xticks([0])
                    axes[ax_i].set_xticklabels(['Whisper large-v3'])
                    axes[ax_i].grid(axis='y', alpha=0.25)
                    med = np.median(speeds)
                    axes[ax_i].axhline(med, ls=':', color='#2C3E50', alpha=0.4)
                    axes[ax_i].text(0.35, med, f'中位数: {med:.2f}', fontsize=9, va='bottom')

            fig.suptitle('Faster-Whisper 转录质量分析', fontsize=14, fontweight='bold', y=1.02)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, '2_transcription_quality.png'),
                        dpi=300, bbox_inches='tight')
            plt.close()

        # ══════════════════════════════════════════════════════════════
        # Figure 3: 每文件字幕产出统计
        # ══════════════════════════════════════════════════════════════
        if self.results.get('subtitle_counts'):
            fig, ax = plt.subplots(figsize=(8, 5.5))

            sub_counts = np.array(self.results['subtitle_counts'])
            sns.histplot(sub_counts, bins=20, kde=True, color='steelblue',
                         edgecolor='white', alpha=0.7, ax=ax)
            ax.axvline(np.mean(sub_counts), color='#E74C3C', ls='--',
                        label=f'均值: {np.mean(sub_counts):.1f}')
            ax.axvline(np.median(sub_counts), color='#F39C12', ls='--',
                        label=f'中位数: {np.median(sub_counts):.1f}')
            ax.set_xlabel('字幕条数 / 文件', fontsize=11)
            ax.set_ylabel('频次', fontsize=11)
            ax.set_title('每文件字幕产出分布', fontsize=12, fontweight='bold')
            ax.legend(fontsize=9)
            ax.grid(axis='y', alpha=0.25)

            fig.suptitle('Faster-Whisper 输出分布', fontsize=14, fontweight='bold', y=1.02)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, '3_output_distribution.png'),
                        dpi=300, bbox_inches='tight')
            plt.close()

        self._generate_report(output_dir)
        print(f"评估完成！图表已保存至: {os.path.abspath(output_dir)}")

    def _generate_report(self, output_dir: str):
        """生成文本报告"""
        report_lines = ["=== Whisper 模型评估报告 ===\n"]
        
        if 'file_paths' in self.results and self.results['file_paths']:
            report_lines.append("【基本统计】")
            report_lines.append(f"  处理文件数: {len(self.results['file_paths'])}")
            
            if 'audio_durations' in self.results and self.results['audio_durations']:
                total_audio = sum(self.results['audio_durations'])
                report_lines.append(f"  总音频时长: {total_audio:.2f}s ({total_audio/60:.2f} 分钟)")
            
            if 'total_process_times' in self.results and self.results['total_process_times']:
                total_time = sum(self.results['total_process_times'])
                report_lines.append(f"  总处理时间: {total_time:.2f}s ({total_time/60:.2f} 分钟)")
            elif 'process_times' in self.results and self.results['process_times']:
                total_time = sum(self.results['process_times'])
                report_lines.append(f"  总处理时间: {total_time:.2f}s ({total_time/60:.2f} 分钟)")
            
            report_lines.append("")
        
        if 'real_time_factors' in self.results and self.results['real_time_factors']:
            rtfs = [r for r in self.results['real_time_factors'] if r > 0]
            if rtfs:
                report_lines.append("【性能指标】")
                report_lines.append(f"  平均实时因子: {np.mean(rtfs):.3f}x")
                report_lines.append(f"  中位数实时因子: {np.median(rtfs):.3f}x")
                report_lines.append(f"  最快: {np.min(rtfs):.3f}x")
                report_lines.append(f"  最慢: {np.max(rtfs):.3f}x")
                report_lines.append("")
        
        if 'subtitle_counts' in self.results and self.results['subtitle_counts']:
            counts = self.results['subtitle_counts']
            report_lines.append("【字幕统计】")
            report_lines.append(f"  总字幕条数: {sum(counts)}")
            report_lines.append(f"  平均每文件字幕数: {np.mean(counts):.1f}")
            report_lines.append("")
        
        if 'total_chars' in self.results and self.results['total_chars']:
            chars = self.results['total_chars']
            report_lines.append("【文字统计】")
            report_lines.append(f"  总识别字符数: {sum(chars)}")
            report_lines.append(f"  平均每文件字符数: {np.mean(chars):.1f}")
            report_lines.append("")
        
        if 'detected_languages' in self.results and self.results['detected_languages']:
            lang_counter = Counter(self.results['detected_languages'])
            report_lines.append("【语言检测】")
            for lang, count in lang_counter.most_common(10):
                report_lines.append(f"  {lang}: {count} 个文件 ({count/len(self.results['detected_languages'])*100:.1f}%)")
            report_lines.append("")
        
        if 'segment_durations' in self.results and self.results['segment_durations']:
            durations = [d for d in self.results['segment_durations'] if d > 0]
            if durations:
                report_lines.append("【片段时长】")
                report_lines.append(f"  平均片段时长: {np.mean(durations):.2f}s")
                report_lines.append(f"  中位数片段时长: {np.median(durations):.2f}s")
                report_lines.append("")
        
        if 'chars_per_second' in self.results and self.results['chars_per_second']:
            speeds = [s for s in self.results['chars_per_second'] if s > 0]
            if speeds:
                report_lines.append("【语速统计】")
                report_lines.append(f"  平均语速: {np.mean(speeds):.2f} 字符/秒")
                report_lines.append(f"  中位语速: {np.median(speeds):.2f} 字符/秒")
                report_lines.append("")
        
        report_text = '\n'.join(report_lines)
        
        with open(os.path.join(output_dir, 'report.txt'), 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print(report_text)


if __name__ == "__main__":
    # 设置模型路径
    current_file = Path(__file__).resolve()
    BASE_DIR = current_file.parent.parent.parent  # video 目录
    MODEL_PATH = BASE_DIR / "video" / "models" / "whisper-ct2-large-v3"
    
    if not MODEL_PATH.exists():
        # 备用路径
        MODEL_PATH = Path("E:/Web/video_web/backend/video/video/models/whisper-ct2-large-v3")
    
    evaluator = WhisperEvaluator(str(MODEL_PATH))
    
    # 使用项目已有的测试视频
    VIDEO_DIR = "E:/Web/video_web/backend/video/media/videos/uploads"
    
    if os.path.exists(VIDEO_DIR):
        import glob
        videos = glob.glob(os.path.join(VIDEO_DIR, "**/*.mp4"), recursive=True)
        if videos:
            print(f"\n找到 {len(videos)} 个测试视频")
            # 评估视频文件夹
            evaluator.evaluate_video_files(VIDEO_DIR, limit=min(4, len(videos)))
            evaluator.plot_results("whisper_eval_videos")
        else:
            print("未找到测试视频")
    else:
        print(f"测试目录不存在: {VIDEO_DIR}")
        print("请修改 VIDEO_DIR 为你的测试视频目录")
