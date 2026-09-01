"""Cloud AI provider contracts and registry."""

from .base import (
    ModerationProvider,
    ModerationResult,
    OCRBlock,
    OCRProvider,
    OCRResult,
    ProviderConfigurationError,
    ProviderError,
    ProviderJob,
    ProviderUnavailableError,
    SpeechToTextProvider,
    TextGenerationResult,
    TextProvider,
    TranscriptSegment,
    TranscriptionResult,
)
from .registry import get_provider, register_provider

__all__ = [
    'ModerationProvider',
    'ModerationResult',
    'OCRBlock',
    'OCRProvider',
    'OCRResult',
    'ProviderConfigurationError',
    'ProviderError',
    'ProviderJob',
    'ProviderUnavailableError',
    'SpeechToTextProvider',
    'TextGenerationResult',
    'TextProvider',
    'TranscriptSegment',
    'TranscriptionResult',
    'get_provider',
    'register_provider',
]
