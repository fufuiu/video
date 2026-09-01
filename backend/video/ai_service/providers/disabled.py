from .base import (
    ModerationProvider,
    OCRProvider,
    ProviderUnavailableError,
    SpeechToTextProvider,
    TextProvider,
)


class DisabledTextProvider(TextProvider):
    async def complete(self, messages, *, temperature=0.3, max_tokens=None):
        raise ProviderUnavailableError('文本 AI 服务未启用', provider='disabled', retryable=False)


class DisabledSpeechToTextProvider(SpeechToTextProvider):
    def submit(self, file_url, *, language='auto'):
        raise ProviderUnavailableError('语音识别服务未启用', provider='disabled', retryable=False)

    def result(self, job_id):
        raise ProviderUnavailableError('语音识别服务未启用', provider='disabled', retryable=False)


class DisabledOCRProvider(OCRProvider):
    def recognize(self, image_bytes):
        raise ProviderUnavailableError('OCR 服务未启用', provider='disabled', retryable=False)


class DisabledModerationProvider(ModerationProvider):
    def submit(self, file_url):
        raise ProviderUnavailableError('内容审核服务未启用', provider='disabled', retryable=False)

    def result(self, job_id):
        raise ProviderUnavailableError('内容审核服务未启用', provider='disabled', retryable=False)
