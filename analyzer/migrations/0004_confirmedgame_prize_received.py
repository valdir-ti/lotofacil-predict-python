from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analyzer', '0003_betconferencerun_confirmedgame'),
    ]

    operations = [
        migrations.AddField(
            model_name='confirmedgame',
            name='prize_received',
            field=models.BooleanField(default=False, verbose_name='Recebido'),
        ),
    ]
