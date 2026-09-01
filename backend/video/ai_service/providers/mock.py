from .base import (
    ModerationProvider,
    ModerationResult,
    OCRBlock,
    OCRProvider,
    OCRResult,
    ProviderJob,
    SpeechToTextProvider,
    TextGenerationResult,
    TextProvider,
    TranscriptSegment,
    TranscriptionResult,
)


class MockTextProvider(TextProvider):
    async def complete(self, messages, *, temperature=0.3, max_tokens=None):
        return TextGenerationResult(
            content='Mock AI response',
            provider='mock',
            model='mock-text',
            request_id='mock-text-request',
            usage={'input_tokens': 0, 'output_tokens': 0},
        )


class MockSpeechToTextProvider(SpeechToTextProvider):
    def submit(self, file_url, *, language='auto'):
        return ProviderJob(provider='mock', job_id='mock-asr-job')

    def result(self, job_id):
        return TranscriptionResult(
            segments=[TranscriptSegment(start=0.0, end=1.0, text='Mock subtitle')],
            provider='mock',
            language='zh',
            duration=1.0,
            request_id='mock-asr-request',
        )


class MockOCRProvider(OCRProvider):
    def recognize(self, image_bytes):
        return OCRResult(
            blocks=[OCRBlock(text='Mock OCR', confidence=1.0)],
            provider='mock',
            request_id='mock-ocr-request',
        )


class MockModerationProvider(ModerationProvider):
    def submit(self, file_url):
        return ProviderJob(provider='mock', job_id='mock-moderation-job')

    def result(self, job_id):
        return ModerationResult(
            decision='review',
            provider='mock',
            confidence=0.5,
            labels=[{'name': 'mock', 'confidence': 0.5}],
            request_id='mock-moderation-request',
        )
