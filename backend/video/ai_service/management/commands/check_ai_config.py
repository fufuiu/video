from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ai_service.providers import ProviderConfigurationError, get_provider


class Command(BaseCommand):
    help = 'Validate configured AI providers without sending external requests.'

    def handle(self, *args, **options):
        errors = []
        cloud_file_capabilities = []
        for capability in ('text', 'asr', 'ocr', 'moderation'):
            setting_name = f'AI_{capability.upper()}_PROVIDER'
            provider_name = str(getattr(settings, setting_name, 'disabled')).strip().lower()
            if capability in {'asr', 'moderation'} and provider_name not in {'disabled', 'mock'}:
                cloud_file_capabilities.append(capability)
            try:
                provider = get_provider(capability)
            except ProviderConfigurationError as exc:
                errors.append(f'{capability}: {exc.safe_message}')
                self.stderr.write(self.style.ERROR(f'{capability}: invalid ({provider_name})'))
                continue
            self.stdout.write(self.style.SUCCESS(f'{capability}: ready ({provider_name})'))
            close = getattr(provider, 'close', None)
            if callable(close):
                close()

        storage_name = str(getattr(settings, 'AI_STORAGE_PROVIDER', 'local')).strip().lower()
        storage_errors = []
        if storage_name in {'aliyun', 'aliyun-oss'}:
            storage_errors = [
                setting_name
                for setting_name in (
                    'ALIYUN_OSS_ENDPOINT',
                    'ALIYUN_OSS_BUCKET',
                    'ALIBABA_CLOUD_ACCESS_KEY_ID',
                    'ALIBABA_CLOUD_ACCESS_KEY_SECRET',
                )
                if not str(getattr(settings, setting_name, '')).strip()
            ]
        if storage_errors:
            errors.append(f'storage: missing {", ".join(storage_errors)}')
            self.stderr.write(self.style.ERROR(f'storage: invalid ({storage_name})'))
        elif cloud_file_capabilities and storage_name not in {'aliyun', 'aliyun-oss'}:
            errors.append(
                'AI_STORAGE_PROVIDER must be aliyun when cloud ASR or moderation is enabled'
            )
            self.stderr.write(self.style.ERROR(f'storage: invalid ({storage_name})'))
        else:
            self.stdout.write(self.style.SUCCESS(f'storage: ready ({storage_name})'))

        if errors:
            raise CommandError(f'AI configuration has {len(errors)} error(s)')
        self.stdout.write(self.style.SUCCESS('AI configuration validation passed; no API request was sent.'))
