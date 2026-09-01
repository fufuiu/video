import subprocess

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
