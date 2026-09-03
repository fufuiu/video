"""
AI 服务异步任务
使用 Celery shared_task 装饰器定义任务
"""
import asyncio
import os
import time
from pathlib import Path
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import ModerationResult, VideoSummary
from .services import OCRService
from core.task_lifecycle import enqueue_task, report_task_progress
import logging

logger = logging.getLogger(__name__)


def _cleanup_temporary_object(storage, stored_object, *, task_name, video_id):
    """Best-effort immediate cleanup for every terminal or retry path."""
    if not storage or not stored_object:
        return True
    try:
        storage.delete(stored_object.key)
        return True
    except Exception as cleanup_error:
        logger.warning(
            'AI temporary object cleanup failed task=%s video_id=%s exception_type=%s',
            task_name,
            video_id,
            type(cleanup_error).__name__,
        )
        return False


def _build_moderation_events(video_file_path, video_id, labels):
    from ai_service.media import extract_moderation_frame
    from ai_service.moderation import group_label_events

    events = group_label_events(labels)
    output_dir = Path(settings.MEDIA_ROOT) / 'ai_moderation' / 'flagged_frames' / str(video_id)
    for index, event in enumerate(events, start=1):
        timestamp_ms = int(round(float(event['timestamp']) * 1000))
        filename = f'incident-{index:03d}-{timestamp_ms}.jpg'
        try:
            extract_moderation_frame(
                video_file_path,
                output_dir / filename,
                event['timestamp'],
            )
            event['image_path'] = filename
        except Exception as exc:
            logger.warning(
                'Moderation evidence frame extraction failed video_id=%s timestamp=%s exception_type=%s',
                video_id,
                event['timestamp'],
                type(exc).__name__,
            )
    return events


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def generate_video_subtitles(self, video_id, language='auto'):
    """
    使用配置的云端 ASR Provider 生成视频字幕。
    
    Args:
        video_id: 视频ID
        language: 语言代码（'auto' 为自动检测）
    """
    from videos.models import Video
    
    task_id = self.request.id or 'unknown'
    report_task_progress(self, current=0, message='开始生成字幕', target_video_id=video_id)
    logger.info(f"[Task {task_id}] 开始生成字幕: video_id={video_id}")
    
    from ai_service.media import extract_audio_for_asr
    from ai_service.providers import ProviderError, ProviderJob, ProviderUnavailableError, get_provider
    from ai_service.storage import get_temporary_storage

    tmp_audio_path = None
    provider = None
    storage = None
    stored_object = None
    
    try:
        video = Video.objects.get(id=video_id)
        
        if not video.video_file:
            raise FileNotFoundError('视频文件不存在')
        
        video_file_path = video.video_file.path
        max_input_bytes = int(getattr(settings, 'AI_CLOUD_MAX_INPUT_BYTES', 2 * 1024 * 1024 * 1024))
        if os.path.exists(video_file_path) and Path(video_file_path).stat().st_size > max_input_bytes:
            raise ProviderUnavailableError('视频超过云端处理大小限制', provider='storage', retryable=False)
        if not os.path.exists(video_file_path):
            raise FileNotFoundError('视频文件路径无效')
        
        # 创建临时目录
        tmp_dir = Path(settings.MEDIA_ROOT) / 'tmp'
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_audio_path = tmp_dir / f"asr_{video_id}_{task_id}.mp3"

        logger.info('[Task %s] 提取云端识别音频', task_id)
        extract_audio_for_asr(video_file_path, tmp_audio_path)
        storage = get_temporary_storage()
        stored_object = storage.upload_file(tmp_audio_path, purpose='asr')
        file_url = storage.signed_download_url(stored_object.key)
        provider = get_provider('asr')
        job = provider.submit(file_url, language=language)
        report_task_progress(
            self,
            current=15,
            message='云端字幕任务已提交',
            target_video_id=video_id,
            metadata={'provider': job.provider, 'provider_job_id': job.job_id},
        )

        deadline = time.monotonic() + int(getattr(settings, 'DASHSCOPE_POLL_TIMEOUT_SECONDS', 1500))
        poll_interval = max(1, int(getattr(settings, 'DASHSCOPE_POLL_INTERVAL_SECONDS', 10)))
        while True:
            result = provider.result(job.job_id)
            if not isinstance(result, ProviderJob):
                break
            if time.monotonic() >= deadline:
                raise ProviderUnavailableError('语音识别任务等待超时', provider=job.provider)
            time.sleep(poll_interval)

        subtitles = [
            {
                'startTime': segment.start,
                'endTime': segment.end,
                'text': segment.text,
                'translation': '',
            }
            for segment in result.segments
        ]
        
        # 更新视频字幕信息
        video.subtitles_draft = subtitles
        video.has_subtitle = len(subtitles) > 0
        video.subtitle_type = 'soft' if video.has_subtitle else 'none'
        video.subtitle_language = result.language
        video.subtitle_detected_at = timezone.now()
        
        if video.status == 'uploading':
            video.status = 'pending_subtitle_edit'
            video.is_published = False  # 重置发布状态
        
        video.save(update_fields=[
            'subtitles_draft',
            'has_subtitle',
            'subtitle_type',
            'subtitle_language',
            'subtitle_detected_at',
            'status',
            'is_published'
        ])
        
        logger.info('[Task %s] 字幕生成完成 count=%s language=%s', task_id, len(subtitles), result.language)
        
        report_task_progress(self, current=100, message='字幕生成完成', target_video_id=video_id)
        return {
            "status": "success",
            "video_id": video_id,
            "count": len(subtitles),
            "subtitle_language": result.language,
            "provider": result.provider,
            "provider_request_id": result.request_id,
        }
        
    except Video.DoesNotExist:
        logger.error('[Task %s] 视频不存在 video_id=%s', task_id, video_id)
        raise
    except ProviderError as exc:
        logger.warning(
            '[Task %s] 字幕 Provider 失败 provider=%s code=%s',
            task_id,
            exc.provider,
            exc.code,
        )
        if exc.retryable and self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise
    except Exception as e:
        logger.error('[Task %s] 字幕生成失败 exception_type=%s', task_id, type(e).__name__, exc_info=True)
        
        if self.request.retries < self.max_retries:
            logger.warning(f"[Task {task_id}] 将重试...")
            raise self.retry(exc=e)
        
        raise
    
    finally:
        # 清理临时文件
        if tmp_audio_path and os.path.exists(tmp_audio_path):
            try:
                os.remove(tmp_audio_path)
                logger.info(f"[Task {task_id}] 已删除临时音频文件")
            except Exception:
                pass
        _cleanup_temporary_object(
            storage,
            stored_object,
            task_name='generate_video_subtitles',
            video_id=video_id,
        )
        if provider:
            close = getattr(provider, 'close', None)
            if callable(close):
                close()


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def detect_video_subtitle(self, video_id):
    """
    检测视频字幕（软字幕 + 硬字幕）
    
    Args:
        video_id: 视频ID
    """
    from videos.models import Video
    
    task_id = self.request.id or 'unknown'
    report_task_progress(self, current=0, message='开始检测字幕', target_video_id=video_id)
    logger.info(f"[Task {task_id}] 开始字幕检测: video_id={video_id}")
    
    try:
        video = Video.objects.get(id=video_id)
        
        if not video.video_file:
            logger.error(f"[Task {task_id}] 视频文件不存在")
            # 字幕检测失败，但允许继续（设置为无字幕）
            video.has_subtitle = False
            video.subtitle_type = 'none'
            video.subtitle_language = ''
            video.status = 'pending_subtitle_edit'
            video.is_published = False
            video.save(update_fields=['has_subtitle', 'subtitle_type', 'subtitle_language', 'status', 'is_published'])
            return {
                "status": "error",
                "reason": "file_not_found",
                "allow_continue": True,
                "subtitle_info": {
                    "has_subtitle": False,
                    "subtitle_type": "none",
                    "subtitle_language": ""
                }
            }
        
        video_file_path = video.video_file.path
        if not os.path.exists(video_file_path):
            logger.error(f"[Task {task_id}] 视频文件路径无效: {video_file_path}")
            # 字幕检测失败，但允许继续
            video.has_subtitle = False
            video.subtitle_type = 'none'
            video.subtitle_language = ''
            video.status = 'pending_subtitle_edit'
            video.is_published = False
            video.save(update_fields=['has_subtitle', 'subtitle_type', 'subtitle_language', 'status', 'is_published'])
            return {
                "status": "error",
                "reason": "file_not_found",
                "allow_continue": True,
                "subtitle_info": {
                    "has_subtitle": False,
                    "subtitle_type": "none",
                    "subtitle_language": ""
                }
            }
        
        logger.info(f"[Task {task_id}] 视频文件: {video_file_path}")
        
        # 使用 OCR 服务检测字幕
        ocr = OCRService()
        result = ocr.detect_subtitle(video_file_path)
        
        logger.info(f"[Task {task_id}] 检测结果: {result}")
        
        # 更新视频字幕信息
        video.has_subtitle = result['has_subtitle']
        video.subtitle_type = result['subtitle_type']
        video.subtitle_language = result['subtitle_language']
        video.subtitle_detected_at = timezone.now()
        
        # 根据检测结果设置视频状态
        if not result['has_subtitle'] or result['subtitle_type'] == 'soft':
            video.status = 'pending_subtitle_edit'
            video.is_published = False
            logger.info(f"[Task {task_id}] 设置状态为 pending_subtitle_edit")
            
            video.save(update_fields=[
                'has_subtitle',
                'subtitle_type',
                'subtitle_language',
                'subtitle_detected_at',
                'status',
                'is_published'
            ])
            
        elif result['subtitle_type'] == 'hard':
            video.status = 'processing'
            logger.info(f"[Task {task_id}] 检测到硬字幕，设置状态为 processing")
            
            video.save(update_fields=[
                'has_subtitle',
                'subtitle_type',
                'subtitle_language',
                'subtitle_detected_at',
                'status'
            ])
            
            # 触发转码任务
            from videos.tasks import process_video
            try:
                enqueue_task(process_video, video_id, target_video_id=video_id)
                logger.info(f"[Task {task_id}] 已触发转码任务")
            except Exception as e:
                logger.error(f"[Task {task_id}] 触发转码任务失败: {e}")
                # 回到允许用户重新触发转码的有效状态，避免写入模型未定义的 uploaded。
                video.status = 'pending_subtitle_edit'
                video.save(update_fields=['status'])
                raise
        else:
            video.save(update_fields=[
                'has_subtitle',
                'subtitle_type',
                'subtitle_language',
                'subtitle_detected_at'
            ])
        
        logger.info(f"[Task {task_id}] 字幕检测完成: has_subtitle={result['has_subtitle']}, type={result['subtitle_type']}")
        
        report_task_progress(self, current=100, message='字幕检测完成', target_video_id=video_id)
        return {
            "status": "success",
            "video_id": video_id,
            "subtitle_info": {
                "has_subtitle": result['has_subtitle'],
                "subtitle_type": result['subtitle_type'],
                "subtitle_language": result['subtitle_language']
            },
            "video_status": video.status
        }
        
    except Video.DoesNotExist:
        logger.error(f"[Task {task_id}] 视频不存在: video_id={video_id}")
        return {
            "status": "error",
            "reason": "video_not_found",
            "allow_continue": False,
            "subtitle_info": {
                "has_subtitle": False,
                "subtitle_type": "none",
                "subtitle_language": ""
            }
        }
    
    except Exception as e:
        logger.error(
            '[Task %s] 字幕检测失败 exception_type=%s',
            task_id,
            type(e).__name__,
            exc_info=True,
        )
        
        # 如果还有重试次数，继续重试
        if getattr(e, 'retryable', True) and self.request.retries < self.max_retries:
            logger.warning(f"[Task {task_id}] 将重试...")
            raise self.retry(exc=e)
        
        # 重试次数用完，设置为无字幕状态，允许用户继续
        try:
            video = Video.objects.get(id=video_id)
            video.has_subtitle = False
            video.subtitle_type = 'none'
            video.subtitle_language = ''
            video.status = 'pending_subtitle_edit'
            video.is_published = False
            video.save(update_fields=['has_subtitle', 'subtitle_type', 'subtitle_language', 'status', 'is_published'])
            logger.warning(f"[Task {task_id}] 字幕检测失败，已设置为无字幕状态，允许用户继续")
        except Exception as save_error:
            logger.error(
                '[Task %s] 保存字幕失败状态出错 exception_type=%s',
                task_id,
                type(save_error).__name__,
            )
        
        return {
            "status": "error",
            "reason": getattr(e, "code", "AI_PROVIDER_UNAVAILABLE"),
            "message": getattr(e, "safe_message", "字幕检测失败，请稍后重试"),
            "allow_continue": True,
            "subtitle_info": {
                "has_subtitle": False,
                "subtitle_type": "none",
                "subtitle_language": ""
            }
        }


def _legacy_local_moderate_video(self, video_id, threshold_level='medium', threshold=0.6, fps=1):
    """
    异步执行视频 NSFW 内容审核
    
    Args:
        video_id: 视频 ID
        threshold_level: 检测级别 (low/medium/high)
        threshold: 置信度阈值
        fps: 每秒抽取帧数
    """
    from videos.models import Video
    from .services import NSFWDetector
    from django.conf import settings
    
    task_id = self.request.id or 'unknown'
    report_task_progress(self, current=0, message='开始内容审核', target_video_id=video_id)
    logger.info(f"[Task {task_id}] 开始 NSFW 审核: video_id={video_id}")
    
    moderation = None
    detector = NSFWDetector()
    frames_dir = None
    
    try:
        video = Video.objects.get(id=video_id)
        
        if not video.video_file:
            raise ValueError("视频文件不存在")
        
        video_file_path = video.video_file.path
        if not os.path.exists(video_file_path):
            raise ValueError(f"视频文件路径无效: {video_file_path}")
        
        # 创建或获取审核记录
        moderation, created = ModerationResult.objects.get_or_create(
            video_id=video_id,
            defaults={'status': 'processing'}
        )
        
        if not created:
            moderation.status = 'processing'
            moderation.error_message = ''
            moderation.save(update_fields=['status', 'error_message'])
        
        # 模型路径
        model_path = os.path.join(
            settings.BASE_DIR,
            'video',
            'models',
            'EVA-based_Fast_NSFW_Image_Classifier'
        )
        
        if not os.path.exists(model_path):
            raise ValueError(f"NSFW 模型不存在: {model_path}")
        
        # 创建保存问题帧的目录
        frames_dir = os.path.join(
            settings.MEDIA_ROOT,
            'ai_moderation',
            'flagged_frames',
            str(video_id)
        )
        Path(frames_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[Task {task_id}] 开始检测，参数: level={threshold_level}, threshold={threshold}, fps={fps}")
        logger.info(f"[Task {task_id}] 问题帧保存目录: {frames_dir}")
        
        # 执行检测（带进度回调）
        def progress_callback(current, total, flagged_frames):
            """进度回调函数"""
            progress = int((current / total) * 100) if total > 0 else 0
            
            # 更新任务状态
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': current,
                    'total': total,
                    'progress': progress,
                    'flagged_count': len(flagged_frames),
                    'flagged_frames': flagged_frames[-10:] if len(flagged_frames) > 10 else flagged_frames  # 只返回最新10个
                }
            )
            
            # 更新数据库记录（每10帧更新一次）
            if current % 10 == 0 or current == total:
                try:
                    moderation.details = {
                        'progress': progress,
                        'current_frame': current,
                        'total_frames': total,
                        'flagged_count': len(flagged_frames),
                        'threshold_level': threshold_level,
                        'threshold': threshold,
                        'fps': fps
                    }
                    moderation.flagged_frames = flagged_frames
                    moderation.save(update_fields=['details', 'flagged_frames'])
                except Exception as e:
                    logger.error(f"[Task {task_id}] 更新进度失败: {e}")
        
        result = detector.detect_video(
            video_path=video_file_path,
            model_path=model_path,
            threshold_level=threshold_level,
            threshold=threshold,
            fps=fps,
            batch_size=4,
            save_frames=True,
            frames_dir=frames_dir,
            progress_callback=progress_callback  # 传入进度回调
        )
        
        # 直接使用模型返回的累积概率
        max_scores = result['max_scores']
        
        # 直接使用模型输出，与 README 保持一致
        neutral_score = max_scores.get('neutral', 0.0)  # 正常内容
        low_score = max_scores.get('low', 0.0)          # 低风险及以上
        medium_score = max_scores.get('medium', 0.0)    # 中风险及以上
        high_score = max_scores.get('high', 0.0)        # 高风险
        
        # 判断审核结果和置信度
        if result['is_safe']:
            moderation_result = 'safe'
            confidence = neutral_score
        elif medium_score >= 0.7:
            moderation_result = 'unsafe'
            confidence = medium_score
        else:
            moderation_result = 'uncertain'
            confidence = medium_score
        
        # 更新审核记录
        moderation.status = 'completed'
        moderation.result = moderation_result
        moderation.confidence = confidence
        moderation.neutral_score = neutral_score
        moderation.low_score = low_score
        moderation.medium_score = medium_score
        moderation.high_score = high_score
        moderation.flagged_frames = result['flagged_frames']
        moderation.details = {
            'total_frames': result['total_frames'],
            'flagged_count': result['flagged_count'],
            'max_scores': result['max_scores'],
            'threshold_level': threshold_level,
            'threshold': threshold,
            'fps': fps,
            'frames_dir': f'ai_moderation/flagged_frames/{video_id}',
            'progress': 100
        }
        moderation.save()
        
        logger.info(f"[Task {task_id}] 审核完成: result={moderation_result}, confidence={confidence:.2f}")
        report_task_progress(self, current=100, message='内容审核完成', target_video_id=video_id)
        
        return {
            'video_id': video_id,
            'status': 'completed',
            'result': moderation_result,
            'confidence': confidence,
            'flagged_count': result['flagged_count']
        }
        
    except Video.DoesNotExist:
        logger.error(f"[Task {task_id}] 视频不存在: video_id={video_id}")
        return {'video_id': video_id, 'status': 'error', 'reason': 'video_not_found'}
    
    except Exception as e:
        logger.error(f"[Task {task_id}] 审核失败: {str(e)}", exc_info=True)
        
        if moderation:
            moderation.status = 'failed'
            moderation.error_message = str(e)
            moderation.save(update_fields=['status', 'error_message'])
        
        # 重试
        if self.request.retries < self.max_retries:
            logger.warning(f"[Task {task_id}] 将重试...")
            raise self.retry(exc=e)
        
        return {'video_id': video_id, 'status': 'error', 'reason': str(e)}
    
    finally:
        # 释放模型资源
        try:
            detector.release_model()
        except Exception:
            pass


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def moderate_video_task(self, video_id, *_legacy_local_args):
    """Moderate a video through the configured cloud provider and temporary storage."""
    from ai_service.providers import ProviderError, ProviderJob, ProviderUnavailableError, get_provider
    from ai_service.storage import get_temporary_storage
    from videos.models import Video

    moderation = None
    provider = None
    storage = None
    stored = None

    try:
        report_task_progress(self, current=0, message='开始云端内容审核', target_video_id=video_id)
        video = Video.objects.get(id=video_id)
        if not video.video_file:
            raise ProviderUnavailableError('视频文件不存在', provider='storage', retryable=False)
        video_file_path = Path(video.video_file.path)
        max_input_bytes = int(getattr(settings, 'AI_CLOUD_MAX_INPUT_BYTES', 2 * 1024 * 1024 * 1024))
        if video_file_path.is_file() and video_file_path.stat().st_size > max_input_bytes:
            raise ProviderUnavailableError('视频超过云端处理大小限制', provider='storage', retryable=False)
        if not video_file_path.is_file():
            raise ProviderUnavailableError('视频文件不存在', provider='storage', retryable=False)

        moderation, _created = ModerationResult.objects.update_or_create(
            video_id=video_id,
            defaults={
                'status': 'processing',
                'result': None,
                'confidence': 0.0,
                'neutral_score': 0.0,
                'low_score': 0.0,
                'medium_score': 0.0,
                'high_score': 0.0,
                'flagged_frames': [],
                'error_message': '',
                'human_decision': 'pending',
                'human_reviewer': None,
                'human_reviewed_at': None,
                'human_review_remark': '',
            },
        )
        storage = get_temporary_storage()
        stored = storage.upload_file(video_file_path, purpose='moderation/video')
        file_url = storage.signed_download_url(stored.key)
        provider = get_provider('moderation')
        job = provider.submit(file_url)
        report_task_progress(
            self,
            current=10,
            message='云端审核任务已提交',
            target_video_id=video_id,
            metadata={'provider': job.provider, 'provider_job_id': job.job_id},
        )

        deadline = time.monotonic() + int(
            getattr(settings, 'ALIYUN_MODERATION_POLL_TIMEOUT_SECONDS', 1800)
        )
        poll_interval = max(
            1, int(getattr(settings, 'ALIYUN_MODERATION_POLL_INTERVAL_SECONDS', 15))
        )
        while True:
            cloud_result = provider.result(job.job_id)
            if not isinstance(cloud_result, ProviderJob):
                break
            if time.monotonic() >= deadline:
                raise ProviderUnavailableError('阿里云视频审核等待超时', provider=job.provider)
            report_task_progress(
                self,
                current=50,
                message='云端内容审核处理中',
                target_video_id=video_id,
                metadata={'provider': job.provider, 'provider_job_id': job.job_id},
            )
            time.sleep(poll_interval)

        result_mapping = {'safe': 'safe', 'review': 'uncertain', 'reject': 'unsafe'}
        moderation_result = result_mapping.get(cloud_result.decision, 'uncertain')
        confidence = max(0.0, min(1.0, float(cloud_result.confidence or 0.0)))
        flagged_frames = _build_moderation_events(
            video_file_path,
            video_id,
            cloud_result.labels,
        )
        moderation.status = 'completed'
        moderation.result = moderation_result
        moderation.confidence = confidence
        # Cloud labels are not cumulative NSFW probabilities. Keep legacy scores empty.
        moderation.neutral_score = 1.0 if moderation_result == 'safe' else 0.0
        moderation.low_score = 0.0
        moderation.medium_score = 0.0
        moderation.high_score = 0.0
        moderation.flagged_frames = flagged_frames
        review_history = list(
            (moderation.details or {}).get('human_review_history') or []
        )
        moderation.details = {
            'provider': cloud_result.provider,
            'provider_job_id': job.job_id,
            'request_id': cloud_result.request_id,
            'decision': cloud_result.decision,
            'labels': cloud_result.labels,
            'input_bytes': stored.size,
            'strategy': 'managed_in_aliyun_console',
            'incident_count': len(flagged_frames),
            'progress': 100,
        }
        if review_history:
            moderation.details['human_review_history'] = review_history
        moderation.error_message = ''
        moderation.save()
        report_task_progress(
            self,
            current=100,
            message='云端内容审核完成',
            target_video_id=video_id,
            metadata={'provider': cloud_result.provider, 'provider_job_id': job.job_id},
        )
        return {
            'video_id': video_id,
            'status': 'completed',
            'result': moderation_result,
            'confidence': confidence,
            'flagged_count': len(flagged_frames),
            'provider': cloud_result.provider,
        }
    except Video.DoesNotExist:
        return {'video_id': video_id, 'status': 'error', 'reason': 'video_not_found'}
    except ProviderError as exc:
        logger.warning(
            'Cloud moderation failed video_id=%s provider=%s code=%s',
            video_id,
            exc.provider,
            exc.code,
        )
        if moderation:
            moderation.status = 'failed'
            moderation.error_message = exc.safe_message
            moderation.save(update_fields=['status', 'error_message'])
        if exc.retryable and self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {'video_id': video_id, 'status': 'error', 'reason': exc.code}
    except Exception as exc:
        logger.exception(
            'Unexpected cloud moderation failure video_id=%s exception_type=%s',
            video_id,
            type(exc).__name__,
        )
        if moderation:
            moderation.status = 'failed'
            moderation.error_message = '内容审核暂时不可用'
            moderation.save(update_fields=['status', 'error_message'])
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {'video_id': video_id, 'status': 'error', 'reason': 'AI_PROVIDER_UNAVAILABLE'}
    finally:
        _cleanup_temporary_object(
            storage,
            stored,
            task_name='moderate_video_task',
            video_id=video_id,
        )


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def summarize_video_task(self, video_id):
    """Generate a real summary and tags through the configured text Provider."""
    from ai_service.providers import ProviderError
    from ai_service.services.deepseek_service import DeepSeekService
    from videos.models import Video

    try:
        report_task_progress(self, current=0, message='开始生成摘要', target_video_id=video_id)
        video = Video.objects.get(id=video_id)
        subtitle_text = '\n'.join(
            str(item.get('text', '')).strip()
            for item in (video.subtitles_draft or [])
            if isinstance(item, dict) and item.get('text')
        )
        max_chars = int(getattr(settings, 'AI_TEXT_MAX_INPUT_CHARS', 50000))
        source_text = (
            f'标题：{video.title}\n描述：{video.description or ""}\n字幕：{subtitle_text}'
        )[:max_chars]

        service = DeepSeekService()

        async def generate_metadata():
            return await asyncio.gather(
                service.generate_video_summary(source_text),
                service.generate_video_tags(video.title, video.description or '', subtitle_text[:max_chars]),
            )

        summary_text, tags = asyncio.run(generate_metadata())
        summary, _created = VideoSummary.objects.update_or_create(
            video_id=video_id,
            defaults={
                'summary': summary_text,
                'key_frames': [],
                'auto_tags': tags,
                'details': {
                    'provider': getattr(service.provider, 'name', 'configured-provider'),
                    'model': service.model,
                    'source': 'subtitle' if subtitle_text else 'metadata',
                },
            },
        )

        report_task_progress(self, current=100, message='摘要生成完成', target_video_id=video_id)
        logger.info('视频摘要生成完成 video_id=%s provider=%s', video_id, summary.details.get('provider'))
        return {
            'video_id': video_id,
            'status': 'completed',
            'summary_id': summary.id,
            'tag_count': len(tags),
        }
    except Video.DoesNotExist:
        logger.warning('视频摘要任务目标不存在 video_id=%s', video_id)
        raise
    except ProviderError as exc:
        logger.warning(
            '视频摘要 Provider 失败 video_id=%s provider=%s code=%s',
            video_id,
            exc.provider,
            exc.code,
        )
        if exc.retryable and self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise
    except Exception as e:
        logger.exception('视频摘要生成失败 video_id=%s exception_type=%s', video_id, type(e).__name__)
        raise


@shared_task
def batch_moderate_videos(video_ids, *_legacy_local_args):
    """
    批量审核视频
    
    Args:
        video_ids: 视频 ID 列表
        云端审核策略由阿里云控制台统一管理。
    """
    results = []
    for video_id in video_ids:
        try:
            result = enqueue_task(
                moderate_video_task,
                video_id,
                target_video_id=video_id,
                dedupe_key=f'video:{video_id}:moderation',
            )
            results.append({'video_id': video_id, 'task_id': result.id, 'status': 'submitted'})
        except Exception as e:
            logger.error(
                '提交视频 %s 审核任务失败 exception_type=%s',
                video_id,
                type(e).__name__,
            )
            results.append({
                'video_id': video_id,
                'error': 'AI_TASK_DISPATCH_FAILED',
                'status': 'failed',
            })
    
    return results
