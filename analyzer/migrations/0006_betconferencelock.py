from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('analyzer', '0005_dailybetresult_owner'),
    ]

    operations = [
        migrations.CreateModel(
            name='BetConferenceLock',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(default='global', max_length=32, unique=True)),
            ],
            options={
                'verbose_name': 'Trava de conferencia',
                'verbose_name_plural': 'Travas de conferencia',
            },
        ),
    ]
