import math

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ai_service.providers.base import ProviderError
from ai_service.storage import get_temporary_storage


class Command(BaseCommand):
    help = 'Inspect or configure the OSS lifecycle rule for AI temporary objects.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Write the lifecycle rule. Without this flag the command is read-only.',
        )

    def handle(self, *args, **options):
        storage = get_temporary_storage()
        if not hasattr(storage, 'get_expiration_lifecycle'):
            raise CommandError('当前 AI_STORAGE_PROVIDER 不是阿里云 OSS')

        retention_hours = int(getattr(settings, 'ALIYUN_OSS_TEMP_RETENTION_HOURS', 24))
        expected_days = max(1, math.ceil(retention_hours / 24))
        try:
            current = storage.get_expiration_lifecycle()
            if not options['apply']:
                self.stdout.write(
                    f'dry-run: current={current or "missing"}; expected_prefix='
                    f'{str(storage.prefix).strip("/")}/; expected_days={expected_days}'
                )
                return

            configured = storage.configure_expiration_lifecycle(
                retention_hours=retention_hours
            )
            verified = storage.get_expiration_lifecycle()
        except ProviderError as exc:
            raise CommandError(exc.safe_message) from exc

        if not verified or verified.get('days') != configured['days']:
            raise CommandError('OSS 生命周期规则写入后复核失败')
        self.stdout.write(
            self.style.SUCCESS(
                f'lifecycle configured: prefix={verified["prefix"]} days={verified["days"]}'
            )
        )
