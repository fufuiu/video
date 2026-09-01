import asyncio
import logging

from django.conf import settings

from .base import (
    ProviderConfigurationError,
    ProviderUnavailableError,
    TextGenerationResult,
    TextProvider,
)


logger = logging.getLogger(__name__)


class DeepSeekTextProvider(TextProvider):
    name = 'deepseek'

    def __init__(self):
        api_key = getattr(settings, 'DEEPSEEK_API_KEY', '').strip()
        if not api_key:
            raise ProviderConfigurationError('DeepSeek API Key 未配置', provider=self.name)

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ProviderConfigurationError('缺少 OpenAI 兼容客户端依赖', provider=self.name) from exc

        self.model = getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-v4-flash')
        self.max_retries = max(0, int(getattr(settings, 'AI_PROVIDER_MAX_RETRIES', 2)))
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=getattr(settings, 'DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
            timeout=float(getattr(settings, 'AI_PROVIDER_TIMEOUT_SECONDS', 60)),
            max_retries=0,
        )

    async def complete(self, messages, *, temperature=0.3, max_tokens=None):
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False,
                )
                usage = {}
                if getattr(response, 'usage', None) is not None:
                    model_dump = getattr(response.usage, 'model_dump', None)
                    usage = model_dump() if callable(model_dump) else {}
                return TextGenerationResult(
                    content=response.choices[0].message.content or '',
                    provider=self.name,
                    model=self.model,
                    request_id=str(getattr(response, 'id', '') or ''),
                    usage=usage,
                )
            except Exception as exc:
                if attempt >= self.max_retries:
                    logger.error('DeepSeek request failed after retries', exc_info=True)
                    raise ProviderUnavailableError(provider=self.name) from exc
                await asyncio.sleep(min(2 ** attempt, 4))

        raise ProviderUnavailableError(provider=self.name)
