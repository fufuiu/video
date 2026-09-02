import subprocess
from pathlib import Path

from django.conf import settings


def extract_audio_for_asr(video_path, output_path):
    """Extract compact mono audio without invoking a shell."""
    command = [
        'ffmpeg',
        '-y',
        '-i',
        str(video_path),
        '-vn',
        '-ac',
        '1',
        '-ar',
        '16000',
        '-codec:a',
        'libmp3lame',
        '-b:a',
        '64k',
        str(output_path),
    ]
    subprocess.run(
        command,
        check=True,
        capture_output=True,
        timeout=int(getattr(settings, 'AI_AUDIO_EXTRACT_TIMEOUT_SECONDS', 900)),
    )


def extract_moderation_frame(video_path, output_path, timestamp):
    """Extract one exact local frame for durable human review."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        'ffmpeg',
        '-y',
        '-i',
        str(video_path),
        '-ss',
        f'{max(0.0, float(timestamp)):.3f}',
        '-frames:v',
        '1',
        '-q:v',
        '2',
        str(output),
    ]
    subprocess.run(
        command,
        check=True,
        capture_output=True,
        timeout=int(getattr(settings, 'AI_MODERATION_FRAME_EXTRACT_TIMEOUT_SECONDS', 30)),
    )
    return output
