from django.core.validators import MinValueValidator
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

	def __str__(self):
		if self.concurso:
			return f'{self.play_date} - concurso {self.concurso}'
		return str(self.play_date)
