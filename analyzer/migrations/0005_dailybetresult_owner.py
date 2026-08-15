from django.conf import settings
from django.db import migrations, models


LEGACY_EMAIL = 'valdir.ti@gmail.com'


def assign_legacy_owner(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    DailyBetResult = apps.get_model('analyzer', 'DailyBetResult')

    user, _created = User.objects.get_or_create(
        email=LEGACY_EMAIL,
        defaults={'username': LEGACY_EMAIL},
    )
    DailyBetResult.objects.filter(owner__isnull=True).update(owner=user)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('analyzer', '0004_confirmedgame_prize_received'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailybetresult',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name='daily_bet_results',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Usuario',
            ),
        ),
        migrations.RemoveConstraint(
            model_name='dailybetresult',
            name='unique_active_daily_bet_result_date',
        ),
        migrations.AddConstraint(
            model_name='dailybetresult',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_active', True)),
                fields=('owner', 'play_date'),
                name='unique_active_daily_bet_result_owner_date',
            ),
        ),
        migrations.RunPython(assign_legacy_owner, migrations.RunPython.noop),
    ]
