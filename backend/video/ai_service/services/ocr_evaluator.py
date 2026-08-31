"""
OCR 模型评估工具 (无监督评估)
评估 PaddleOCR 的性能和输出分布
"""
import os
import time
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from PIL import Image
import sys
from pathlib import Path
from collections import Counter
import json

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 设置 ModelScope 缓存目录
os.environ['MODELSCOPE_CACHE'] = 'E:/.cache/modelscope'

# 添加当前目录到 sys.path
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

class OCREvaluator:
    """OCR 模型评估工具 (无监督评估)"""

    def __init__(self, models_dir: str = None):
        """
        Args:
            models_dir: 模型目录路径，默认使用 E:/Web/video_web/backend/video/video/models
        """
        self.models_dir = models_dir
        self.ocr = None
        self.results = []

    def _load_ocr(self):
        """加载 OCR 模型"""
        if self.ocr is not None:
            return self.ocr
        
        try:
            from paddleocr import PaddleOCR
            import gc
            
            # 设置环境变量
            os.environ['DISABLE_MODEL_SOURCE_CHECK'] = 'True'
            
            # 模型路径
            if self.models_dir:
                models_path = Path(self.models_dir)
            else:
                models_path = Path("E:/Web/video_web/backend/video/video/models")
            
            det_model_dir = models_path / 'PP-OCRv5_server_det'
            rec_model_dir = models_path / 'PP-OCRv5_server_rec'
            
            print(f"检测模型路径: {det_model_dir}")
            print(f"识别模型路径: {rec_model_dir}")
            
            if not det_model_dir.exists() or not rec_model_dir.exists():
                print(f"OCR 模型未找到")
                return None
            
            self.ocr = PaddleOCR(
                text_detection_model_dir=str(det_model_dir),
                text_recognition_model_dir=str(rec_model_dir),
                use_textline_orientation=False,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                lang='ch',
                ocr_version='PP-OCRv5'
            )
            
            print("PaddleOCR 加载成功")
            return self.ocr
            
        except Exception as e:
            print(f"PaddleOCR 加载失败: {e}")
            return None

    def evaluate_folder(self, folder_path: str, limit: int = 1000, 
                        subtitle_area_only: bool = False):
        """
        评估文件夹中的图片
        
        Args:
            folder_path: 图片文件夹路径
            limit: 最大评估图片数
            subtitle_area_only: 是否只检测字幕区域
            
        Returns:
            评估结果字典
        """
        import glob
        
        print(f"正在评估文件夹: {folder_path}")
        
        # 加载模型
        ocr = self._load_ocr()
        if not ocr:
            print("OCR 模型加载失败")
            return None
        
        # 获取图片列表
        extensions = ('*.png', '*.jpg', '*.jpeg', '*.webp', '*.bmp')
        files = []
        for ext in extensions:
            files.extend(glob.glob(os.path.join(folder_path, ext)))
            files.extend(glob.glob(os.path.join(folder_path, '**', ext), recursive=True))
        
        files = list(set(files))[:limit]
        print(f"找到 {len(files)} 张图片")
        
        results = {
            'image_paths': [],
            'process_times': [],
            'text_counts': [],
            'total_chars': [],
            'avg_confidences': [],
            'all_texts': [],
            'all_confidences': [],
            'box_positions': [],  # [(x1, y1, x2, y2), ...]
            'box_sizes': [],      # [width, height, ...]
            'text_lengths': [],
            'detected_frames': 0,
            'subtitle_area_detections': [],
        }
        
        for img_path in tqdm(files, desc="Processing images"):
            try:
                start_time = time.time()
                
                # 获取图片尺寸
                img = Image.open(img_path)
                img_width, img_height = img.size
                img.close()
                
                # OCR 检测
                ocr_result = ocr.predict(img_path)
                process_time = time.time() - start_time
                
                # 解析结果
                texts = []
                confidences = []
                boxes = []
                subtitle_detected = False
                
                if ocr_result and len(ocr_result) > 0:
                    for page_result in ocr_result:
                        if hasattr(page_result, 'json'):
                            json_data = page_result.json
                            
                            if isinstance(json_data, dict) and 'res' in json_data:
                                res = json_data['res']
                                if isinstance(res, dict) and 'rec_texts' in res and 'rec_boxes' in res:
                                    rec_texts = res.get('rec_texts', [])
                                    rec_boxes = res.get('rec_boxes', [])
                                    rec_scores = res.get('rec_scores', [])
                                    
                                    for i, (text, box) in enumerate(zip(rec_texts, rec_boxes)):
                                        if not text or not box:
                                            continue
                                        
                                        texts.append(text)
                                        boxes.append(box)
                                        
                                        # 置信度
                                        if i < len(rec_scores):
                                            confidences.append(rec_scores[i])
                                        else:
                                            confidences.append(1.0)
                                        
                                        # 检测框位置和大小
                                        x1, y1, x2, y2 = box
                                        width = x2 - x1
                                        height = y2 - y1
                                        results['box_sizes'].append((width, height))
                                        results['box_positions'].append((x1, y1, x2, y2))
                                        
                                        # 判断是否在字幕区域（底部 30%）
                                        center_y = (y1 + y2) / 2
                                        if center_y >= img_height * 0.7:
                                            subtitle_detected = True
                                
                                results['text_lengths'].extend([len(t) for t in texts if t])
                
                results['image_paths'].append(img_path)
                results['process_times'].append(process_time)
                results['text_counts'].append(len(texts))
                results['total_chars'].append(sum(len(t) for t in texts))
                results['all_texts'].extend(texts)
                results['all_confidences'].extend(confidences)
                results['subtitle_area_detections'].append(subtitle_detected)
                
                if confidences:
                    results['avg_confidences'].append(np.mean(confidences))
                else:
                    results['avg_confidences'].append(0)
                
                if texts:
                    results['detected_frames'] += 1
                    
            except Exception as e:
                print(f"处理失败 {img_path}: {e}")
                continue
        
        self.results = results
        return results

    def evaluate_video_frames(self, video_path: str, sample_count: int = 50):
        """
        评估视频帧的 OCR 性能
        
        Args:
            video_path: 视频文件路径
            sample_count: 采样帧数
            
        Returns:
            评估结果字典
        """
        import tempfile
        import subprocess
        
        print(f"正在评估视频: {video_path}")
        
        # 加载模型
        ocr = self._load_ocr()
        if not ocr:
            print("OCR 模型加载失败")
            return None
        
        # 获取视频时长
        duration = self._get_video_duration(video_path)
        if duration <= 0:
            print("无法获取视频时长")
            return None
        
        # 计算采样时间点
        sample_times = self._calculate_sample_times(duration, sample_count)
        
        results = {
            'video_path': video_path,
            'sample_times': [],
            'process_times': [],
            'text_counts': [],
            'total_chars': [],
            'avg_confidences': [],
            'all_texts': [],
            'subtitle_detections': [],
            'frame_consistency': [],
        }
        
        prev_texts = None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            for i, time_point in enumerate(tqdm(sample_times, desc="Processing frames")):
                frame_path = os.path.join(temp_dir, f'frame_{i}.jpg')
                
                # 提取帧
                if not self._extract_frame(video_path, time_point, frame_path):
                    continue
                
                try:
                    start_time = time.time()
                    ocr_result = ocr.predict(frame_path)
                    process_time = time.time() - start_time
                    
                    # 解析结果
                    texts = []
                    confidences = []
                    subtitle_detected = False
                    
                    if ocr_result and len(ocr_result) > 0:
                        img = Image.open(frame_path)
                        img_height = img.size[1]
                        img.close()
                        
                        for page_result in ocr_result:
                            if hasattr(page_result, 'json'):
                                json_data = page_result.json
                                
                                if isinstance(json_data, dict) and 'res' in json_data:
                                    res = json_data['res']
                                    if isinstance(res, dict):
                                        rec_texts = res.get('rec_texts', [])
                                        rec_boxes = res.get('rec_boxes', [])
                                        rec_scores = res.get('rec_scores', [])
                                        
                                        for j, (text, box) in enumerate(zip(rec_texts, rec_boxes)):
                                            if text and box:
                                                texts.append(text)
                                                if j < len(rec_scores):
                                                    confidences.append(rec_scores[j])
                                                
                                                # 字幕区域检测
                                                x1, y1, x2, y2 = box
                                                center_y = (y1 + y2) / 2
                                                if center_y >= img_height * 0.7:
                                                    subtitle_detected = True
                    
                    # 计算帧间一致性
                    if prev_texts is not None:
                        similarity = self._text_similarity(prev_texts, texts)
                        results['frame_consistency'].append(similarity)
                    prev_texts = texts
                    
                    results['sample_times'].append(time_point)
                    results['process_times'].append(process_time)
                    results['text_counts'].append(len(texts))
                    results['total_chars'].append(sum(len(t) for t in texts))
                    results['all_texts'].extend(texts)
                    results['subtitle_detections'].append(subtitle_detected)
                    
                    if confidences:
                        results['avg_confidences'].append(np.mean(confidences))
                    else:
                        results['avg_confidences'].append(0)
                        
                except Exception as e:
                    print(f"帧处理失败: {e}")
                    continue
        
        self.results = results
        return results

    def _get_video_duration(self, video_path: str) -> float:
        """获取视频时长"""
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                   '-of', 'json', video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return float(data.get('format', {}).get('duration', 0))
        except Exception as e:
            print(f"获取时长失败: {e}")
        return 0

    def _calculate_sample_times(self, duration: float, count: int):
        """计算采样时间点"""
        if count <= 1:
            return [duration / 2]
        return [duration * i / (count - 1) for i in range(count)]

    def _extract_frame(self, video_path: str, time_point: float, output_path: str) -> bool:
        """提取视频帧"""
        try:
            cmd = ['ffmpeg', '-ss', str(time_point), '-i', video_path,
                   '-vframes', '1', '-q:v', '2', '-y', output_path]
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            return result.returncode == 0 and os.path.exists(output_path)
        except Exception as e:
            return False

    def _text_similarity(self, texts1: list, texts2: list) -> float:
        """计算两组文本的相似度 (Jaccard)"""
        if not texts1 and not texts2:
            return 1.0
        if not texts1 or not texts2:
            return 0.0
        
        set1 = set(''.join(texts1))
        set2 = set(''.join(texts2))
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0

    def plot_results(self, output_dir: str = "ocr_evaluation_results"):
        """生成学术级评估图表 (精选 3-4 张代表性图)"""
        if not self.results:
            print("没有评估结果")
            return
        
        from scipy import stats as scipy_stats
        
        os.makedirs(output_dir, exist_ok=True)

        # ══════════════════════════════════════════════════════════════
        # Figure 1: 性能总览 — 处理时间 CDF + 置信度 CDF
        # ══════════════════════════════════════════════════════════════
        if self.results.get('process_times') and self.results.get('all_confidences'):
            fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(14, 5.5))

            times = np.array(self.results['process_times'])
            confs = np.array(self.results['all_confidences'])

            # (a) 处理时间 CDF
            sorted_t = np.sort(times)
            cdf_t = np.arange(1, len(sorted_t) + 1) / len(sorted_t)
            ax0.fill_between(sorted_t, 0, cdf_t, alpha=0.15, color='steelblue')
            ax0.plot(sorted_t, cdf_t, color='steelblue', lw=2.2)
            for pct, ls in [(50, ':'), (95, '--')]:
                val = np.percentile(times, pct)
                ax0.axvline(val, color='#E74C3C', ls=ls, lw=1.4,
                            label=f'P{pct}: {val:.3f}s')
            ax0.set_xlabel('处理时间 (秒)', fontsize=11)
            ax0.set_ylabel('累积概率', fontsize=11)
            ax0.set_title('(a) 处理时间累积分布', fontsize=12, fontweight='bold')
            ax0.legend(fontsize=9, framealpha=0.9)
            ax0.grid(alpha=0.25)
            ax0.set_ylim(0, 1.02)

            # (b) 置信度 CDF
            sorted_c = np.sort(confs)
            cdf_c = np.arange(1, len(sorted_c) + 1) / len(sorted_c)
            ax1.fill_between(sorted_c, 0, cdf_c, alpha=0.15, color='darkorange')
            ax1.plot(sorted_c, cdf_c, color='darkorange', lw=2.2)
            for thresh, col in [(0.8, '#3498DB'), (0.9, '#E74C3C')]:
                ratio = (confs >= thresh).mean()
                ax1.axvline(thresh, ls='--', lw=1.4, color=col,
                            label=f'≥{thresh}: {ratio*100:.1f}%')
            ax1.set_xlabel('识别置信度', fontsize=11)
            ax1.set_ylabel('累积概率', fontsize=11)
            ax1.set_title('(b) 置信度累积分布', fontsize=12, fontweight='bold')
            ax1.legend(fontsize=9, framealpha=0.9)
            ax1.grid(alpha=0.25)
            ax1.set_ylim(0, 1.02)

            fig.suptitle('PaddleOCR 性能评估总览', fontsize=14, fontweight='bold', y=1.02)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, '1_performance_overview.png'),
                        dpi=300, bbox_inches='tight')
            plt.close()

        # ══════════════════════════════════════════════════════════════
        # Figure 2: 检测质量分析 — 置信度分布小提琴图 + 处理时间vs复杂度回归
        # ══════════════════════════════════════════════════════════════
        if self.results.get('all_confidences') and self.results.get('process_times'):
            fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

            # (a) 置信度 Violin + Strip
            confs = np.array(self.results['all_confidences'])
            parts = axes[0].violinplot(confs, positions=[0], showmeans=True,
                                        showmedians=True, showextrema=False)
            for pc in parts['bodies']:
                pc.set_facecolor('#F39C12')
                pc.set_alpha(0.35)
            parts['cmeans'].set_color('#E74C3C')
            parts['cmedians'].set_color('#2C3E50')
            np.random.seed(42)
            jitter = np.random.normal(0, 0.02, len(confs))
            sample_idx = np.random.choice(len(confs), min(300, len(confs)), replace=False)
            axes[0].scatter(jitter[sample_idx], confs[sample_idx],
                            alpha=0.25, s=8, color='#E67E22', zorder=2)
            axes[0].axhline(0.9, ls='--', color='#E74C3C', alpha=0.6, label='阈值 0.9')
            axes[0].axhline(0.8, ls='--', color='#3498DB', alpha=0.6, label='阈值 0.8')
            axes[0].set_ylabel('置信度', fontsize=11)
            axes[0].set_title('(a) 置信度分布', fontsize=12, fontweight='bold')
            axes[0].set_xticks([0])
            axes[0].set_xticklabels(['PaddleOCR v5'])
            axes[0].legend(fontsize=9)
            axes[0].grid(axis='y', alpha=0.25)

            # (b) 处理时间 vs 文字块数量 回归散点
            if self.results.get('text_counts'):
                times = np.array(self.results['process_times'])
                counts = np.array(self.results['text_counts'])
                scatter = axes[1].scatter(counts, times, c=times, cmap='coolwarm',
                                          alpha=0.6, s=25, edgecolors='white', lw=0.3)
                plt.colorbar(scatter, ax=axes[1], label='处理时间 (秒)', shrink=0.85)
                if len(counts) > 2 and np.std(counts) > 0:
                    z = np.polyfit(counts, times, 1)
                    p = np.poly1d(z)
                    x_line = np.linspace(counts.min(), counts.max(), 100)
                    axes[1].plot(x_line, p(x_line), color='#E74C3C', ls='--', lw=2)
                    r_val, p_val = scipy_stats.pearsonr(counts, times)
                    axes[1].text(0.05, 0.95, f'r = {r_val:.3f}, p = {p_val:.2e}',
                                 transform=axes[1].transAxes, fontsize=10,
                                 va='top', bbox=dict(boxstyle='round,pad=0.3',
                                                     facecolor='white', alpha=0.85))
                axes[1].set_xlabel('每帧检测文字块数', fontsize=11)
                axes[1].set_ylabel('处理时间 (秒)', fontsize=11)
                axes[1].set_title('(b) 处理时间 vs 复杂度', fontsize=12, fontweight='bold')
                axes[1].grid(alpha=0.25)

            fig.suptitle('PaddleOCR 检测质量分析', fontsize=14, fontweight='bold', y=1.02)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, '2_quality_analysis.png'),
                        dpi=300, bbox_inches='tight')
            plt.close()

        # ══════════════════════════════════════════════════════════════
        # Figure 3: 空间分布 — 检测密度热力图
        # ══════════════════════════════════════════════════════════════
        if self.results.get('box_positions'):
            fig, ax = plt.subplots(figsize=(9, 6.5))

            positions = np.array(self.results['box_positions'])
            cx = (positions[:, 0] + positions[:, 2]) / 2
            cy = (positions[:, 1] + positions[:, 3]) / 2

            from scipy.ndimage import gaussian_filter
            h_data, xedges, yedges = np.histogram2d(cx, cy, bins=60)
            h_smooth = gaussian_filter(h_data.T, sigma=1.5)
            extent = [xedges[0], xedges[-1], yedges[-1], yedges[0]]
            im = ax.imshow(h_smooth, extent=extent, aspect='auto',
                           cmap='magma_r', interpolation='bicubic')
            plt.colorbar(im, ax=ax, label='检测密度', shrink=0.85)
            ax.set_xlabel('X 坐标 (px)', fontsize=11)
            ax.set_ylabel('Y 坐标 (px)', fontsize=11)
            ax.set_title('检测密度热力图', fontsize=12, fontweight='bold')

            fig.suptitle('PaddleOCR 文字检测空间分布', fontsize=14, fontweight='bold', y=1.02)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, '3_spatial_distribution.png'),
                        dpi=300, bbox_inches='tight')
            plt.close()

        self._generate_report(output_dir)
        print(f"评估完成！图表已保存至: {os.path.abspath(output_dir)}")

    def _generate_report(self, output_dir: str):
        """生成文本报告"""
        report_lines = ["=== OCR 模型评估报告 ===\n"]
        
        if 'process_times' in self.results and self.results['process_times']:
            times = self.results['process_times']
            report_lines.append("【处理性能】")
            report_lines.append(f"  总处理图片数: {len(times)}")
            report_lines.append(f"  平均处理时间: {np.mean(times):.3f}s")
            report_lines.append(f"  中位数处理时间: {np.median(times):.3f}s")
            report_lines.append(f"  最大处理时间: {np.max(times):.3f}s")
            report_lines.append(f"  最小处理时间: {np.min(times):.3f}s")
            report_lines.append(f"  总耗时: {np.sum(times):.2f}s")
            report_lines.append("")
        
        if 'text_counts' in self.results and self.results['text_counts']:
            counts = self.results['text_counts']
            report_lines.append("【检测统计】")
            report_lines.append(f"  检测到文字的帧数: {self.results.get('detected_frames', sum(1 for c in counts if c > 0))}")
            report_lines.append(f"  平均每帧文字块数: {np.mean(counts):.2f}")
            report_lines.append(f"  总检测文字块数: {sum(counts)}")
            report_lines.append("")
        
        if 'all_confidences' in self.results and self.results['all_confidences']:
            confs = self.results['all_confidences']
            report_lines.append("【置信度统计】")
            report_lines.append(f"  平均置信度: {np.mean(confs):.3f}")
            report_lines.append(f"  中位数置信度: {np.median(confs):.3f}")
            report_lines.append(f"  置信度 >= 0.9 的比例: {sum(1 for c in confs if c >= 0.9) / len(confs) * 100:.1f}%")
            report_lines.append(f"  置信度 >= 0.8 的比例: {sum(1 for c in confs if c >= 0.8) / len(confs) * 100:.1f}%")
            report_lines.append("")
        
        if 'total_chars' in self.results and self.results['total_chars']:
            chars = self.results['total_chars']
            report_lines.append("【文字统计】")
            report_lines.append(f"  总识别字符数: {sum(chars)}")
            report_lines.append(f"  平均每帧字符数: {np.mean(chars):.2f}")
            report_lines.append("")
        
        if 'subtitle_area_detections' in self.results and self.results['subtitle_area_detections']:
            detections = self.results['subtitle_area_detections']
            report_lines.append("【字幕检测】")
            report_lines.append(f"  检测到字幕的帧数: {sum(detections)}")
            report_lines.append(f"  字幕检测率: {sum(detections) / len(detections) * 100:.1f}%")
            report_lines.append("")
        
        if 'frame_consistency' in self.results and self.results['frame_consistency']:
            consistency = self.results['frame_consistency']
            report_lines.append("【帧间一致性】")
            report_lines.append(f"  平均相似度: {np.mean(consistency):.3f}")
            report_lines.append(f"  最低相似度: {np.min(consistency):.3f}")
            report_lines.append("")
        
        report_text = '\n'.join(report_lines)
        
        with open(os.path.join(output_dir, 'report.txt'), 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print(report_text)

    def release_model(self):
        """释放模型"""
        if self.ocr is not None:
            del self.ocr
            self.ocr = None
            import gc
            gc.collect()
            print("OCR 模型已释放")


if __name__ == "__main__":
    # 设置模型路径
    current_file = Path(__file__).resolve()
    BASE_DIR = current_file.parent.parent.parent  # video 目录
    MODELS_DIR = BASE_DIR / "video" / "models"
    
    if not MODELS_DIR.exists():
        # 备用路径
        MODELS_DIR = Path("E:/Web/video_web/backend/video/video/models")
    
    evaluator = OCREvaluator(str(MODELS_DIR))
    
    # 使用项目已有的测试数据
    TEST_DIRS = [
        "E:/Web/video_web/evaluation_results/error_samples/false_positives",
        "E:/Web/video_web/evaluation_results/error_samples/false_negatives",
    ]
    
    for test_dir in TEST_DIRS:
        if os.path.exists(test_dir):
            print(f"\n使用测试目录: {test_dir}")
            evaluator.evaluate_folder(test_dir, limit=200)
            evaluator.plot_results(f"ocr_eval_{Path(test_dir).name}")
            break
    else:
        # 如果没有找到测试图片，评估视频帧
        VIDEO_DIR = "E:/Web/video_web/backend/video/media/videos/uploads"
        if os.path.exists(VIDEO_DIR):
            import glob
            videos = glob.glob(os.path.join(VIDEO_DIR, "**/*.mp4"), recursive=True)
            if videos:
                print(f"\n使用测试视频: {videos[0]}")
                evaluator.evaluate_video_frames(videos[0], sample_count=30)
                evaluator.plot_results("ocr_eval_video")
            else:
                print("未找到测试数据")
        else:
            print("未找到测试数据，请手动指定 TEST_DIR")
