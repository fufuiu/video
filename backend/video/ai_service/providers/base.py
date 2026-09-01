from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any


class ProviderError(RuntimeError):
    """Stable provider error safe to expose through the task API."""

    def __init__(
        self,
        code: str,
        safe_message: str,
        *,
        provider: str = '',
        retryable: bool = False,
    ):
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.provider = provider
        self.retryable = retryable


class ProviderConfigurationError(ProviderError):
    def __init__(self, safe_message='AI 服务配置不完整', *, provider=''):
        super().__init__('AI_PROVIDER_NOT_CONFIGURED', safe_message, provider=provider, retryable=False)


class ProviderUnavailableError(ProviderError):
    def __init__(self, safe_message='AI 服务暂时不可用，请稍后再试', *, provider='', retryable=True):
        super().__init__('AI_PROVIDER_UNAVAILABLE', safe_message, provider=provider, retryable=retryable)


@dataclass(frozen=True)
class ProviderJob:
    provider: str
    job_id: str
    status: str = 'pending'
    request_id: str = ''

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class TextGenerationResult:
    content: str
    provider: str
    model: str
    request_id: str = ''
    usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptionResult:
    segments: list[TranscriptSegment]
    provider: str
    language: str = ''
    duration: float = 0.0
    request_id: str = ''

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class OCRBlock:
    text: str
    confidence: float = 0.0
    polygon: list[list[float]] = field(default_factory=list)


@dataclass(frozen=True)
class OCRResult:
    blocks: list[OCRBlock]
    provider: str
    request_id: str = ''

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ModerationResult:
    decision: str
    provider: str
    confidence: float = 0.0
    labels: list[dict[str, Any]] = field(default_factory=list)
    request_id: str = ''

    def to_dict(self):
        return asdict(self)


class TextProvider(ABC):
    @abstractmethod
    async def complete(self, messages, *, temperature=0.3, max_tokens=None) -> TextGenerationResult:
        raise NotImplementedError


class SpeechToTextProvider(ABC):
    @abstractmethod
    def submit(self, file_url: str, *, language='auto') -> ProviderJob:
        raise NotImplementedError

    @abstractmethod
    def result(self, job_id: str) -> TranscriptionResult | ProviderJob:
        raise NotImplementedError


class OCRProvider(ABC):
    @abstractmethod
    def recognize(self, image_bytes: bytes) -> OCRResult:
        raise NotImplementedError


class ModerationProvider(ABC):
    @abstractmethod
    def submit(self, file_url: str) -> ProviderJob:
        raise NotImplementedError

    @abstractmethod
    def result(self, job_id: str) -> ModerationResult | ProviderJob:
        raise NotImplementedError
