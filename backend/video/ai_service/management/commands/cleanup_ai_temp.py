from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError

from ai_service.providers.base import ProviderError
from ai_service.storage import get_temporary_storage
from ai_service.storage.aliyun_oss import build_purpose_prefix


class Command(BaseCommand):
    help = 'List or delete OSS AI temporary objects for one exact purpose prefix.'

    def add_arguments(self, parser):
        parser.add_argument('--purpose', default='moderation-video')
        parser.add_argument('--older-than-hours', type=float, default=24.0)
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Delete matching objects. Without this flag the command is read-only.',
        )

    def handle(self, *args, **options):
        storage = get_temporary_storage()
        if not hasattr(storage, 'list_objects'):
            raise CommandError('当前 AI_STORAGE_PROVIDER 不是阿里云 OSS')
        purpose = options['purpose']
        older_than_hours = options['older_than_hours']
        if older_than_hours < 0:
            raise CommandError('older-than-hours 不能小于 0')

        expected_prefix = build_purpose_prefix(purpose=purpose, prefix=storage.prefix)
        cutoff = datetime.now(timezone.utc).timestamp() - older_than_hours * 3600
        try:
            objects = storage.list_objects(purpose=purpose)
        except ProviderError as exc:
            raise CommandError(exc.safe_message) from exc
        candidates = [obj for obj in objects if obj['last_modified'] <= cutoff]
        if any(not obj['key'].startswith(expected_prefix) for obj in candidates):
            raise CommandError('对象前缀核对失败，已停止清理')

        total_bytes = sum(obj['size'] for obj in candidates)
        mode = 'apply' if options['apply'] else 'dry-run'
        self.stdout.write(
            f'{mode}: prefix={expected_prefix} count={len(candidates)} bytes={total_bytes}'
        )
        if not options['apply']:
            return

        deleted = 0
        for obj in candidates:
            try:
                storage.delete(obj['key'])
                deleted += 1
            except ProviderError as exc:
                raise CommandError(
                    f'清理中断：已删除 {deleted}/{len(candidates)} 个对象；{exc.safe_message}'
                ) from exc
        self.stdout.write(self.style.SUCCESS(f'cleanup complete: deleted={deleted}'))
