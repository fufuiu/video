from __future__ import annotations

from collections.abc import Callable

from django.conf import settings

from .base import ProviderConfigurationError
from .disabled import (
    DisabledModerationProvider,
    DisabledOCRProvider,
    DisabledSpeechToTextProvider,
    DisabledTextProvider,
)
from .mock import MockModerationProvider, MockOCRProvider, MockSpeechToTextProvider, MockTextProvider


def _deepseek_text_provider():
    from .deepseek import DeepSeekTextProvider

    return DeepSeekTextProvider()


def _aliyun_asr_provider():
    from .aliyun_asr import AliyunSpeechToTextProvider

    return AliyunSpeechToTextProvider()


def _aliyun_ocr_provider():
    from .aliyun_ocr import AliyunOCRProvider

    return AliyunOCRProvider()


def _aliyun_moderation_provider():
    from .aliyun_moderation import AliyunVideoModerationProvider

    return AliyunVideoModerationProvider()


CAPABILITY_SETTINGS = {
    'text': 'AI_TEXT_PROVIDER',
    'asr': 'AI_ASR_PROVIDER',
    'ocr': 'AI_OCR_PROVIDER',
    'moderation': 'AI_MODERATION_PROVIDER',
}

_PROVIDER_FACTORIES: dict[tuple[str, str], Callable[[], object]] = {
    ('text', 'disabled'): DisabledTextProvider,
    ('asr', 'disabled'): DisabledSpeechToTextProvider,
    ('ocr', 'disabled'): DisabledOCRProvider,
    ('moderation', 'disabled'): DisabledModerationProvider,
    ('text', 'mock'): MockTextProvider,
    ('asr', 'mock'): MockSpeechToTextProvider,
    ('ocr', 'mock'): MockOCRProvider,
    ('moderation', 'mock'): MockModerationProvider,
    ('text', 'deepseek'): _deepseek_text_provider,
    ('asr', 'aliyun'): _aliyun_asr_provider,
    ('asr', 'aliyun-asr'): _aliyun_asr_provider,
    ('ocr', 'aliyun'): _aliyun_ocr_provider,
    ('ocr', 'aliyun-ocr'): _aliyun_ocr_provider,
    ('moderation', 'aliyun'): _aliyun_moderation_provider,
    ('moderation', 'aliyun-green'): _aliyun_moderation_provider,
}


def register_provider(capability: str, name: str, factory: Callable[[], object]):
    key = (capability.strip().lower(), name.strip().lower())
    if key[0] not in CAPABILITY_SETTINGS:
        raise ValueError(f'未知 AI 能力: {capability}')
    _PROVIDER_FACTORIES[key] = factory


def get_provider(capability: str, name: str | None = None):
    capability = capability.strip().lower()
    setting_name = CAPABILITY_SETTINGS.get(capability)
    if not setting_name:
        raise ProviderConfigurationError(f'未知 AI 能力: {capability}')
    provider_name = (name or getattr(settings, setting_name, 'disabled')).strip().lower()
    factory = _PROVIDER_FACTORIES.get((capability, provider_name))
    if factory is None:
        raise ProviderConfigurationError(
            f'{capability} 未注册 Provider: {provider_name}',
            provider=provider_name,
        )
    return factory()
