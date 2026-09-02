"""Subtitle detection using FFprobe/FFmpeg and a configured cloud OCR provider."""

from __future__ import annotations

import io
import json
import logging
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from django.conf import settings

from ai_service.providers import get_provider

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self, provider=None):
        self.provider = provider

    def detect_subtitle(self, video_path: str) -> dict:
        soft_result = self._detect_soft_subtitle(video_path)
        if soft_result['has_subtitle']:
            return {
                'has_subtitle': True,
                'subtitle_type': 'soft',
                'subtitle_language': soft_result.get('language', ''),
                'details': soft_result,
            }

        provider_name = str(getattr(settings, 'AI_OCR_PROVIDER', 'disabled')).strip().lower()
        if self.provider is None and provider_name == 'disabled':
            return {
                'has_subtitle': False,
                'subtitle_type': 'none',
                'subtitle_language': '',
                'details': {
                    'has_subtitle': False,
                    'detected_frames': 0,
                    'total_frames': 0,
                    'language': '',
                    'provider': 'disabled',
                    'skipped': True,
                    'reason': 'ocr_disabled',
                },
            }

        hard_result = self._detect_hard_subtitle(video_path)
        if hard_result['has_subtitle']:
            return {
                'has_subtitle': True,
                'subtitle_type': 'hard',
                'subtitle_language': hard_result.get('language', ''),
                'details': hard_result,
            }
        return {
            'has_subtitle': False,
            'subtitle_type': 'none',
            'subtitle_language': '',
            'details': hard_result,
        }

    def _detect_soft_subtitle(self, video_path: str) -> dict:
        try:
            result = subprocess.run(
                [
                    'ffprobe', '-v', 'error', '-select_streams', 's',
                    '-show_entries', 'stream=index,codec_name,codec_type:stream_tags=language',
                    '-of', 'json', str(video_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return {'has_subtitle': False, 'tracks': [], 'language': ''}
            streams = json.loads(result.stdout).get('streams', [])
            tracks = [
                {
                    'index': stream.get('index'),
                    'codec': stream.get('codec_name'),
                    'language': stream.get('tags', {}).get('language', 'unknown'),
                }
                for stream in streams
            ]
            languages = sorted({
                item['language'] for item in tracks if item['language'] not in {'', 'unknown'}
            })
            return {
                'has_subtitle': bool(tracks),
                'tracks': tracks,
                'language': ','.join(languages) if languages else ('unknown' if tracks else ''),
            }
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            logger.warning('Soft subtitle detection failed: %s', type(exc).__name__)
            return {'has_subtitle': False, 'tracks': [], 'language': ''}

    def _detect_hard_subtitle(self, video_path: str, sample_count: int | None = None) -> dict:
        sample_count = sample_count or int(getattr(settings, 'AI_OCR_SAMPLE_COUNT', 8))
        sample_count = max(2, min(sample_count, 20))
        provider = self.provider or get_provider('ocr')
        duration = self._get_video_duration(video_path)
        if duration <= 0:
            return {'has_subtitle': False, 'detected_frames': 0, 'total_frames': 0, 'language': ''}

        sample_times = self._calculate_sample_times(duration, sample_count)
        detected_count = 0
        processed_count = 0
        with tempfile.TemporaryDirectory() as temp_dir:
            for index, time_point in enumerate(sample_times):
                frame_path = Path(temp_dir) / f'frame_{index}.jpg'
                if not self._extract_frame(video_path, time_point, frame_path):
                    continue
                processed_count += 1
                if self._has_text_in_subtitle_area(frame_path, provider):
                    detected_count += 1

        threshold = max(2, processed_count * 0.3)
        has_subtitle = processed_count > 0 and detected_count >= threshold
        return {
            'has_subtitle': has_subtitle,
            'detected_frames': detected_count,
            'total_frames': processed_count,
            'language': 'zh' if has_subtitle else '',
            'provider': getattr(provider, 'name', ''),
        }

    def _get_video_duration(self, video_path: str) -> float:
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(video_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return float(json.loads(result.stdout).get('format', {}).get('duration', 0))
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        return 0.0

    @staticmethod
    def _calculate_sample_times(duration: float, count: int) -> list[float]:
        if count <= 1:
            return [duration / 2]
        return [
            round(max(0.0, min(duration - 0.01, duration * index / (count - 1))), 2)
            for index in range(count)
        ]

    @staticmethod
    def _extract_frame(video_path: str, time_point: float, output_path: Path) -> bool:
        try:
            result = subprocess.run(
                [
                    'ffmpeg', '-ss', str(time_point), '-i', str(video_path),
                    '-vframes', '1', '-q:v', '3', '-y', str(output_path),
                ],
                capture_output=True,
                timeout=30,
            )
            return result.returncode == 0 and output_path.exists()
        except (OSError, subprocess.SubprocessError):
            return False

    @staticmethod
    def _has_text_in_subtitle_area(image_path: Path, provider) -> bool:
        with Image.open(image_path) as image:
            top = int(image.height * 0.7)
            cropped = image.crop((0, top, image.width, image.height))
            output = io.BytesIO()
            cropped.save(output, format='JPEG', quality=85, optimize=True)
        result = provider.recognize(output.getvalue())
        return any(block.text.strip() for block in result.blocks)

    def release_model(self):
        """Compatibility no-op; cloud OCR does not retain a local model."""
        return None
