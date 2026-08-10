from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class DailyBetResultQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class DailyBetResult(models.Model):
	objects = models.Manager()
	active_objects = DailyBetResultQuerySet.as_manager()

	play_date = models.DateField('Data do jogo')
	concurso = models.PositiveIntegerField('Concurso', null=True, blank=True)
	invested_amount = models.DecimalField(
		'Valor investido',
		max_digits=10,
		decimal_places=2,
		validators=[MinValueValidator(0)],
	)
	returned_amount = models.DecimalField(
		'Valor retornado',
		max_digits=10,
		decimal_places=2,
		validators=[MinValueValidator(0)],
	)
	notes = models.TextField('Observacao', blank=True)
	is_active = models.BooleanField('Ativo', default=True)
	deactivated_at = models.DateTimeField('Desativado em', null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-play_date']
		verbose_name = 'Resultado diario'
		verbose_name_plural = 'Resultados diarios'
		constraints = [
			models.UniqueConstraint(
				fields=['play_date'],
				condition=Q(is_active=True),
				name='unique_active_daily_bet_result_date',
			),
		]

	@property
	def balance(self):
		return self.returned_amount - self.invested_amount

	@property
	def contemplated_games_count(self):
		return sum(1 for game in self.games.all() if game.is_contemplated)

	@property
	def has_contemplated_game(self):
		return self.contemplated_games_count > 0

	def __str__(self):
		if self.concurso:
			return f'{self.play_date} - concurso {self.concurso}'
		return str(self.play_date)


class ConfirmedGame(models.Model):
	SOURCE_AI = 'ai'
	SOURCE_MANUAL = 'manual'
	SOURCE_CHOICES = [
		(SOURCE_AI, 'Gerado pela IA'),
		(SOURCE_MANUAL, 'Manual'),
	]

	daily_result = models.ForeignKey(
		DailyBetResult,
		on_delete=models.CASCADE,
		related_name='games',
		verbose_name='Registro diario',
	)
	dezenas = models.JSONField('Dezenas apostadas')
	concurso = models.PositiveIntegerField('Concurso', null=True, blank=True)
	amount = models.DecimalField(
		'Valor apostado',
		max_digits=10,
		decimal_places=2,
		validators=[MinValueValidator(0)],
	)
	source = models.CharField(
		'Origem', max_length=10, choices=SOURCE_CHOICES, default=SOURCE_AI
	)
	score = models.FloatField('Pontuacao do modelo', null=True, blank=True)
	rationale = models.TextField('Justificativa da IA', blank=True)
	is_checked = models.BooleanField('Conferido', default=False)
	is_contemplated = models.BooleanField('Contemplado', default=False)
	hits_count = models.PositiveSmallIntegerField(
		'Quantidade de acertos',
		null=True,
		blank=True,
		validators=[MaxValueValidator(15)],
	)
	matched_numbers = models.JSONField('Dezenas acertadas', null=True, blank=True)
	prize_amount = models.DecimalField(
		'Valor do premio',
		max_digits=10,
		decimal_places=2,
		null=True,
		blank=True,
		validators=[MinValueValidator(0)],
	)
	prize_received = models.BooleanField('Recebido', default=False)
	checked_at = models.DateTimeField('Conferido em', null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
		verbose_name = 'Jogo confirmado'
		verbose_name_plural = 'Jogos confirmados'

	def __str__(self):
		return f'Jogo {self.pk} - concurso {self.concurso or "?"}'


class BetConferenceRun(models.Model):
	TRIGGER_AUTO = 'auto'
	TRIGGER_MANUAL = 'manual'
	TRIGGER_CHOICES = [
		(TRIGGER_AUTO, 'Automatico'),
		(TRIGGER_MANUAL, 'Manual'),
	]

	checked_at = models.DateTimeField(auto_now_add=True)
	triggered_by = models.CharField(
		'Disparado por', max_length=10, choices=TRIGGER_CHOICES, default=TRIGGER_AUTO
	)
	checked_count = models.PositiveIntegerField('Jogos conferidos', default=0)
	contemplated_count = models.PositiveIntegerField('Jogos contemplados', default=0)

	class Meta:
		ordering = ['-checked_at']
		verbose_name = 'Execucao de conferencia'
		verbose_name_plural = 'Execucoes de conferencia'

	def __str__(self):
		return f'{self.checked_at:%Y-%m-%d %H:%M} ({self.triggered_by})'
