from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from django.conf import settings

from ai_service.providers.base import ProviderConfigurationError, ProviderUnavailableError

from .base import TemporaryObject, TemporaryStorage


def _load_oss2():
    try:
        import oss2
    except ImportError as exc:
        raise ProviderConfigurationError('缺少阿里云 OSS Python SDK（oss2）', provider='aliyun-oss') from exc
    return oss2


def build_object_key(local_path, *, purpose='ai-input', prefix='ai-temp/'):
    suffix = Path(local_path).suffix.lower()
    if not re.fullmatch(r'\.[a-z0-9]{1,10}', suffix):
        suffix = ''
    safe_purpose = re.sub(r'[^a-zA-Z0-9_-]+', '-', str(purpose)).strip('-') or 'ai-input'
    safe_prefix = str(prefix or 'ai-temp/').strip('/')
    date_path = datetime.now(timezone.utc).strftime('%Y/%m/%d')
    return f'{safe_prefix}/{safe_purpose}/{date_path}/{uuid4().hex}{suffix}'


class AliyunOSSTemporaryStorage(TemporaryStorage):
    def __init__(self):
        self.endpoint = getattr(settings, 'ALIYUN_OSS_ENDPOINT', '').strip()
        self.bucket_name = getattr(settings, 'ALIYUN_OSS_BUCKET', '').strip()
        self.prefix = getattr(settings, 'ALIYUN_OSS_PREFIX', 'ai-temp/')
        self.url_ttl = int(getattr(settings, 'ALIYUN_OSS_SIGNED_URL_TTL_SECONDS', 21600))
        self.access_key_id = getattr(settings, 'ALIBABA_CLOUD_ACCESS_KEY_ID', '').strip()
        self.access_key_secret = getattr(settings, 'ALIBABA_CLOUD_ACCESS_KEY_SECRET', '').strip()
        self.security_token = getattr(settings, 'ALIBABA_CLOUD_SECURITY_TOKEN', '').strip()

    def _bucket(self):
        missing = [
            name
            for name, value in (
                ('ALIYUN_OSS_ENDPOINT', self.endpoint),
                ('ALIYUN_OSS_BUCKET', self.bucket_name),
                ('ALIBABA_CLOUD_ACCESS_KEY_ID', self.access_key_id),
                ('ALIBABA_CLOUD_ACCESS_KEY_SECRET', self.access_key_secret),
            )
            if not value
        ]
        if missing:
            raise ProviderConfigurationError(
                f'OSS 配置不完整：{", ".join(missing)}',
                provider='aliyun-oss',
            )

        oss2 = _load_oss2()
        if self.security_token:
            auth = oss2.StsAuth(self.access_key_id, self.access_key_secret, self.security_token)
        else:
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        return oss2.Bucket(auth, self.endpoint, self.bucket_name)

    def upload_file(self, local_path, *, purpose='ai-input'):
        path = Path(local_path).resolve()
        if not path.is_file():
            raise FileNotFoundError('待上传文件不存在')
        key = build_object_key(path, purpose=purpose, prefix=self.prefix)
        try:
            self._bucket().put_object_from_file(key, str(path))
        except ProviderConfigurationError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError('上传 AI 临时文件失败', provider='aliyun-oss') from exc
        return TemporaryObject(provider='aliyun-oss', key=key, size=path.stat().st_size)

    def signed_download_url(self, key):
        try:
            return self._bucket().sign_url('GET', str(key), self.url_ttl, slash_safe=True)
        except ProviderConfigurationError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError('生成 OSS 临时访问地址失败', provider='aliyun-oss') from exc

    def delete(self, key):
        try:
            self._bucket().delete_object(str(key))
        except ProviderConfigurationError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError('清理 OSS 临时文件失败', provider='aliyun-oss') from exc
