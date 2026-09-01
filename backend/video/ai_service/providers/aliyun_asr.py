from __future__ import annotations

from django.conf import settings

from .base import (
    ProviderConfigurationError,
    ProviderJob,
    ProviderUnavailableError,
    SpeechToTextProvider,
    TranscriptSegment,
    TranscriptionResult,
)


def _seconds(value):
    number = float(value or 0)
    return number


def _milliseconds_to_seconds(value):
    return float(value or 0) / 1000


def _duration_seconds(data):
    if data.get('content_duration_in_milliseconds') is not None:
        return _milliseconds_to_seconds(data['content_duration_in_milliseconds'])
    return _seconds(data.get('duration', 0))


def _segment_seconds(data, millisecond_keys, second_keys):
    for key in millisecond_keys:
        if data.get(key) is not None:
            return _milliseconds_to_seconds(data[key])
    for key in second_keys:
        if data.get(key) is not None:
            return _seconds(data[key])
    return 0.0


def parse_transcription_payload(payload, *, request_id=''):
    output = payload.get('output') if isinstance(payload, dict) else None
    root = output if isinstance(output, dict) else payload
    transcripts = root.get('transcripts') or root.get('results') or []
    segments = []
    language = str(root.get('language') or '')
    duration = _duration_seconds(root)

    for transcript in transcripts:
        if not isinstance(transcript, dict):
            continue
        language = language or str(transcript.get('language') or '')
        duration = duration or _duration_seconds(transcript)
        sentences = transcript.get('sentences') or transcript.get('segments') or []
        for sentence in sentences:
            if not isinstance(sentence, dict):
                continue
            text = str(sentence.get('text') or '').strip()
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    start=_segment_seconds(sentence, ('begin_time', 'start_time'), ('start',)),
                    end=_segment_seconds(sentence, ('end_time',), ('end',)),
                    text=text,
                )
            )
        if not sentences and transcript.get('text'):
            segments.append(
                TranscriptSegment(start=0.0, end=duration, text=str(transcript['text']).strip())
            )

    return TranscriptionResult(
        segments=segments,
        provider='aliyun-asr',
        language=language,
        duration=duration,
        request_id=request_id,
    )


class AliyunSpeechToTextProvider(SpeechToTextProvider):
    name = 'aliyun-asr'

    def __init__(self, client=None):
        self.api_key = getattr(settings, 'DASHSCOPE_API_KEY', '').strip()
        self.base_url = getattr(settings, 'DASHSCOPE_BASE_URL', '').strip().rstrip('/')
        self.model = getattr(settings, 'DASHSCOPE_ASR_MODEL', 'fun-asr')
        if not self.api_key or not self.base_url:
            raise ProviderConfigurationError(
                '百炼语音识别需要配置 DASHSCOPE_API_KEY 和 DASHSCOPE_BASE_URL',
                provider=self.name,
            )
        if client is None:
            try:
                import httpx
            except ImportError as exc:
                raise ProviderConfigurationError('缺少 httpx 依赖', provider=self.name) from exc
            client = httpx.Client(timeout=float(getattr(settings, 'AI_PROVIDER_TIMEOUT_SECONDS', 60)))
        self.client = client

    def _headers(self, *, async_request=False):
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        if async_request:
            headers['X-DashScope-Async'] = 'enable'
        return headers

    def submit(self, file_url, *, language='auto'):
        parameters = {}
        if language and language != 'auto':
            parameters['language_hints'] = [language]
        try:
            response = self.client.post(
                f'{self.base_url}/api/v1/services/audio/asr/transcription',
                headers=self._headers(async_request=True),
                json={
                    'model': self.model,
                    'input': {'file_urls': [file_url]},
                    'parameters': parameters,
                },
            )
            response.raise_for_status()
            payload = response.json()
            output = payload.get('output') or {}
            job_id = output.get('task_id') or payload.get('task_id')
            if not job_id:
                raise ValueError('missing task_id')
            return ProviderJob(
                provider=self.name,
                job_id=str(job_id),
                request_id=str(payload.get('request_id') or ''),
            )
        except Exception as exc:
            raise ProviderUnavailableError('提交阿里云语音识别任务失败', provider=self.name) from exc

    def result(self, job_id):
        try:
            response = self.client.get(
                f'{self.base_url}/api/v1/tasks/{job_id}',
                headers=self._headers(),
            )
            response.raise_for_status()
            payload = response.json()
            output = payload.get('output') or {}
            state = str(output.get('task_status') or payload.get('task_status') or '').upper()
            request_id = str(payload.get('request_id') or '')
            if state in {'PENDING', 'RUNNING', 'QUEUED'}:
                return ProviderJob(
                    provider=self.name,
                    job_id=str(job_id),
                    status=state.lower(),
                    request_id=request_id,
                )
            if state not in {'SUCCEEDED', 'SUCCESS'}:
                raise ProviderUnavailableError('阿里云语音识别任务失败', provider=self.name)

            results = output.get('results') or []
            transcription_url = next(
                (
                    item.get('transcription_url')
                    for item in results
                    if isinstance(item, dict) and item.get('transcription_url')
                ),
                None,
            )
            if transcription_url:
                # Do not forward the DashScope bearer token to the signed result URL.
                transcription_response = self.client.get(transcription_url)
                transcription_response.raise_for_status()
                transcription_payload = transcription_response.json()
            else:
                transcription_payload = output
            return parse_transcription_payload(transcription_payload, request_id=request_id)
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError('查询阿里云语音识别结果失败', provider=self.name) from exc

    def close(self):
        close = getattr(self.client, 'close', None)
        if callable(close):
            close()
