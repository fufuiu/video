from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('videos', '0015_add_taken_down_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='video',
            name='status',
            field=models.CharField(
                choices=[
                    ('uploading', '上传中'),
                    ('pending_subtitle_edit', '等待字幕编辑'),
                    ('transcoding', '转码中'),
                    ('processing', '处理中'),
                    ('ready', '就绪'),
                    ('failed', '失败'),
                    ('pending', '待审核'),
                    ('approved', '已通过'),
                    ('rejected', '已拒绝'),
                    ('taken_down', '已下架'),
                ],
                db_index=True,
                default='uploading',
                max_length=30,
                verbose_name='状态',
            ),
        ),
    ]
