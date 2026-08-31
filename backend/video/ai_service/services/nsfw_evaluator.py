import os
import torch
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
from tqdm import tqdm
from PIL import Image
from sklearn.metrics import confusion_matrix, classification_report, roc_curve, auc, precision_recall_curve, average_precision_score
import sys
from pathlib import Path
import shutil

# 设置 ModelScope 缓存目录到 E 盘
os.environ['MODELSCOPE_CACHE'] = 'E:/.cache/modelscope'

# 添加当前目录到 sys.path 以支持导入
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

try:
    from nsfw_service import NSFWDetector
except ImportError:
    from .nsfw_service import NSFWDetector

class NSFWEvaluator:
    """NSFW 模型评估工具 (增强版)"""

    def __init__(self, model_path: str):
        self.detector = NSFWDetector()
        self.model_path = model_path
        self.idx_to_label = {0: 'neutral', 1: 'low', 2: 'medium', 3: 'high'}
        self.label_to_idx = {v: k for k, v in self.idx_to_label.items()}
        
    def _prepare_detector(self):
        """确保模型已加载"""
        self.detector._load_model(self.model_path)

    def plot_results(self, y_true, y_pred, y_scores, image_paths=None, output_dir: str = "evaluation_results", 
                     y_scores_low=None, category_scores=None):
        """生成全套评估图表"""
        if len(y_true) == 0:
            print("没有数据可以生成图表")
            return

        os.makedirs(output_dir, exist_ok=True)
        
        # 1. 混淆矩阵 (Confusion Matrix)
        plt.figure(figsize=(8, 6))
        cm = confusion_matrix(y_true, y_pred)
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                    xticklabels=['正常', '违规'], 
                    yticklabels=['正常', '违规'])
        plt.title('混淆矩阵')
        plt.ylabel('真实标签')
        plt.xlabel('预测标签')
        plt.savefig(os.path.join(output_dir, '1_confusion_matrix.png'), dpi=300)
        plt.close()
        
        # 2. ROC 曲线 (Receiver Operating Characteristic)
        if len(np.unique(y_true)) > 1:
            plt.figure(figsize=(8, 6))
            fpr, tpr, _ = roc_curve(y_true, y_scores)
            roc_auc = auc(fpr, tpr)
            plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC曲线 (AUC = {roc_auc:.2f})')
            plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
            plt.xlim([0.0, 1.0])
            plt.ylim([0.0, 1.05])
            plt.xlabel('误报率 (FPR)')
            plt.ylabel('召回率 (TPR)')
            plt.title('ROC曲线')
            plt.legend(loc="lower right")
            plt.grid(alpha=0.3)
            plt.savefig(os.path.join(output_dir, '2_roc_curve.png'), dpi=300)
            plt.close()

            # 3. Precision-Recall 曲线
            plt.figure(figsize=(8, 6))
            precision, recall, _ = precision_recall_curve(y_true, y_scores)
            avg_precision = average_precision_score(y_true, y_scores)
            plt.plot(recall, precision, color='green', lw=2, label=f'PR曲线 (AP = {avg_precision:.2f})')
            plt.xlabel('召回率 (Recall)')
            plt.ylabel('精确率 (Precision)')
            plt.title('精确率-召回率曲线')
            plt.legend(loc="lower left")
            plt.grid(alpha=0.3)
            plt.savefig(os.path.join(output_dir, '3_pr_curve.png'), dpi=300)
            plt.close()

        # 4. 得分分布图 (Score Distribution) - 按原始类别细分
        plt.figure(figsize=(12, 6))
        import pandas as pd
        
        if category_scores is not None:
            # 按原始5分类绘制分布
            df_scores = pd.DataFrame({
                '得分': y_scores,
                '类别': category_scores['categories'],
                '真实标签': ['正常' if t == 0 else '违规' for t in y_true]
            })
            # 使用不同颜色区分5个类别
            palette = {'neutral': 'skyblue', 'drawings': 'lightgreen', 
                       'sexy': 'orange', 'porn': 'salmon', 'hentai': 'red'}
            sns.histplot(data=df_scores, x='得分', hue='类别', 
                         element="step", kde=True, palette=palette,
                         alpha=0.5, bins=40, stat='density', common_norm=False)
            plt.title('各类别得分分布 (Medium分数)')
        else:
            df_scores = pd.DataFrame({
                '得分': y_scores,
                '真实标签': ['正常' if t == 0 else '违规' for t in y_true]
            })
            sns.histplot(data=df_scores, x='得分', hue='真实标签', 
                         element="step", kde=True, palette={'正常': 'skyblue', '违规': 'salmon'},
                         alpha=0.6, bins=30)
            plt.title('得分分布')
        plt.xlabel('模型得分 (Medium分数)')
        plt.ylabel('密度')
        plt.grid(axis='y', alpha=0.3)
        plt.savefig(os.path.join(output_dir, '4_score_distribution.png'), dpi=300)
        plt.close()
        
        # 4.5 各类别得分箱线图
        if category_scores is not None:
            plt.figure(figsize=(10, 6))
            df_box = pd.DataFrame({
                'Medium分数': category_scores['medium_scores'],
                'Low分数': category_scores['low_scores'],
                '类别': category_scores['categories']
            })
            fig, axes = plt.subplots(1, 2, figsize=(14, 5))
            
            # Medium 分数箱线图
            order = ['neutral', 'drawings', 'sexy', 'porn', 'hentai']
            sns.boxplot(data=df_box, x='类别', y='Medium分数', order=order, ax=axes[0],
                        palette={'neutral': 'skyblue', 'drawings': 'lightgreen', 
                                 'sexy': 'orange', 'porn': 'salmon', 'hentai': 'red'})
            axes[0].axhline(y=0.5, color='red', linestyle='--', label='阈值 0.5')
            axes[0].set_title('各类别 Medium 分数分布')
            axes[0].tick_params(axis='x', rotation=15)
            axes[0].legend(loc='upper right')
            
            # Low 分数箱线图
            sns.boxplot(data=df_box, x='类别', y='Low分数', order=order, ax=axes[1],
                        palette={'neutral': 'skyblue', 'drawings': 'lightgreen', 
                                 'sexy': 'orange', 'porn': 'salmon', 'hentai': 'red'})
            axes[1].axhline(y=0.5, color='red', linestyle='--', label='阈值 0.5')
            axes[1].set_title('各类别 Low 分数分布')
            axes[1].tick_params(axis='x', rotation=15)
            axes[1].legend(loc='upper right')
            
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, '4.5_category_boxplot.png'), dpi=300)
            plt.close()

        # 5. 错误样本分析 (Error Analysis)
        if image_paths is not None:
            error_dir = os.path.join(output_dir, "error_samples")
            if os.path.exists(error_dir):
                shutil.rmtree(error_dir)
            os.makedirs(os.path.join(error_dir, "false_positives"), exist_ok=True) # 误报：正常被看成违规
            os.makedirs(os.path.join(error_dir, "false_negatives"), exist_ok=True) # 漏报：违规被看成正常
            
            for i in range(len(y_true)):
                if y_true[i] == 0 and y_pred[i] == 1: # False Positive
                    shutil.copy(image_paths[i], os.path.join(error_dir, "false_positives", os.path.basename(image_paths[i])))
                elif y_true[i] == 1 and y_pred[i] == 0: # False Negative
                    shutil.copy(image_paths[i], os.path.join(error_dir, "false_negatives", os.path.basename(image_paths[i])))

        # 6. 分类报告 (Text Report)
        report = classification_report(y_true, y_pred, target_names=['正常', '违规'], zero_division=0)
        
        # 6.5 各类别详细统计
        category_stats = ""
        if category_scores is not None:
            category_stats = "\n\n=== 各类别得分统计 ===\n"
            for cat in ['neutral', 'drawings', 'sexy', 'porn', 'hentai']:
                mask = np.array(category_scores['categories']) == cat
                if mask.sum() > 0:
                    cat_medium = np.array(category_scores['medium_scores'])[mask]
                    cat_low = np.array(category_scores['low_scores'])[mask]
                    category_stats += f"\n{cat}:\n"
                    category_stats += f"  样本数: {mask.sum()}\n"
                    category_stats += f"  Medium分数: 均值={cat_medium.mean():.3f}, 中位数={np.median(cat_medium):.3f}, 标准差={cat_medium.std():.3f}\n"
                    category_stats += f"  Low分数: 均值={cat_low.mean():.3f}, 中位数={np.median(cat_low):.3f}\n"
                    category_stats += f"  Medium>=0.5 比例: {(cat_medium >= 0.5).mean()*100:.1f}%\n"
                    category_stats += f"  Low>=0.5 比例: {(cat_low >= 0.5).mean()*100:.1f}%\n"
        
        with open(os.path.join(output_dir, 'report.txt'), 'w', encoding='utf-8') as f:
            f.write("=== NSFW模型评估报告 ===\n\n")
            f.write(report)
            if len(np.unique(y_true)) > 1:
                f.write(f"\nROC AUC: {roc_auc:.4f}")
                f.write(f"\n平均精确率 (AP): {avg_precision:.4f}")
            f.write(category_stats)
        
        print(f"评估完成！全套图表已保存至: {os.path.abspath(output_dir)}")
        print(report)
        print(category_stats)

    def evaluate_on_complex_folder(self, folder_path: str, limit: int = 12000):
        """
        适配 5 分类数据集结构：drawings, hentai, neutral, porn, sexy
        映射逻辑：
        - neutral, drawings -> Label 0 (Normal)
        - porn, hentai      -> Label 1 (NSFW)
        - sexy              -> 判定为边界，默认映射为 1 (NSFW) 以增强安全性，
                               但在分析报告中单独统计各原始类别得分。
        """
        import glob
        print(f"正在从多分类目录加载图片: {folder_path}...")
        
        y_true = []
        y_scores = []  # medium 分数
        y_scores_low = []  # low 分数
        y_pred_labels = []
        all_image_paths = []
        categories = []  # 原始类别名称
        
        # 定义任务列表：(子目录名, 真实标签)
        tasks = [
            ('neutral', 0),
            ('drawings', 0),
            ('porn', 1),
            ('hentai', 1),
            ('sexy', 1) # 性感内容在严苛模式下通常视为违规，也可根据需求改为 0
        ]
        
        self._prepare_detector()
        
        # 计算每个文件夹的限额以保持平衡
        per_folder_limit = limit // len(tasks)
        
        for subfolder, label_idx in tasks:
            path = os.path.join(folder_path, subfolder, "*.*")
            files = glob.glob(path)
            files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
            print(f"目录 {subfolder}: 找到 {len(files)} 张图片，取前 {min(len(files), per_folder_limit)} 张")
            
            files = files[:per_folder_limit]
            
            for f in tqdm(files, desc=f"Processing {subfolder}"):
                try:
                    image = Image.open(f).convert('RGB')
                    result = self.detector.predict_batch([image])[0]
                    
                    y_true.append(label_idx)
                    y_scores.append(result['medium'])
                    y_scores_low.append(result['low'])
                    y_pred_labels.append(1 if result['medium'] >= 0.5 else 0)
                    all_image_paths.append(f)
                    categories.append(subfolder)
                except Exception as e:
                    continue
        
        category_scores = {
            'categories': categories,
            'medium_scores': y_scores,
            'low_scores': y_scores_low
        }
        return np.array(y_true), np.array(y_pred_labels), np.array(y_scores), all_image_paths, category_scores

if __name__ == "__main__":
    # 修正模型路径
    current_file = Path(__file__).resolve()
    BASE_DIR = current_file.parent.parent.parent
    MODEL_PATH = str(BASE_DIR / "video" / "models" / "EVA-based_Fast_NSFW_Image_Classifier")
    
    if not os.path.exists(MODEL_PATH):
        MODEL_PATH = str(BASE_DIR / "models" / "EVA-based_Fast_NSFW_Image_Classifier")
    
    evaluator = NSFWEvaluator(MODEL_PATH)
    
    # 指向你的 5 分类数据集目录
    TEST_DIR = "E:/nsfw_test" 
    
    try:
        # 使用新的多分类扫描函数
        y_true, y_pred, y_scores, image_paths, category_scores = evaluator.evaluate_on_complex_folder(TEST_DIR, limit=12000)
        evaluator.plot_results(y_true, y_pred, y_scores, image_paths=image_paths, 
                              y_scores_low=np.array(category_scores['low_scores']),
                              category_scores=category_scores)
    except Exception as e:
        print(f"运行失败: {e}")
        import traceback
        traceback.print_exc()
