from django.conf import settings

from ai_service.providers.base import ProviderConfigurationError

from .aliyun_oss import AliyunOSSTemporaryStorage
from .local import LocalTemporaryStorage


STORAGE_FACTORIES = {
    'local': LocalTemporaryStorage,
    'oss': AliyunOSSTemporaryStorage,
    'aliyun': AliyunOSSTemporaryStorage,
    'aliyun-oss': AliyunOSSTemporaryStorage,
}


def get_temporary_storage(name=None):
    provider_name = (name or getattr(settings, 'AI_STORAGE_PROVIDER', 'local')).strip().lower()
    factory = STORAGE_FACTORIES.get(provider_name)
    if factory is None:
        raise ProviderConfigurationError(
            f'未注册临时存储 Provider: {provider_name}',
            provider=provider_name,
        )
    return factory()
