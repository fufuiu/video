from pathlib import Path

from ai_service.providers.base import ProviderConfigurationError

from .base import TemporaryObject, TemporaryStorage


class LocalTemporaryStorage(TemporaryStorage):
    """Local placeholder that keeps base startup independent of OSS."""

    def upload_file(self, local_path, *, purpose='ai-input'):
        path = Path(local_path).resolve()
        if not path.is_file():
            raise FileNotFoundError('待上传文件不存在')
        return TemporaryObject(provider='local', key=str(path), size=path.stat().st_size)

    def signed_download_url(self, key):
        raise ProviderConfigurationError('云端 AI 需要配置 OSS 临时存储', provider='local')

    def delete(self, key):
        # Local media belongs to the application; temporary storage must never
        # delete it implicitly.
        return None
