from django import forms
from django.conf import settings

from .models import ConfirmedGame, DailyBetResult
from .services.game_validation import InvalidGameError, validate_numbers


class ExcelUploadForm(forms.Form):
    file = forms.FileField(label='Arquivo Excel (.xlsx)')

    def clean_file(self):
        uploaded_file = self.cleaned_data['file']
        file_name = uploaded_file.name.lower()

        if not file_name.endswith('.xlsx'):
            raise forms.ValidationError('Envie um arquivo .xlsx válido.')

        max_size = getattr(settings, 'FILE_UPLOAD_MAX_MEMORY_SIZE', 10 * 1024 * 1024)
        if uploaded_file.size > max_size:
            raise forms.ValidationError('Arquivo excede o limite de tamanho permitido.')

        return uploaded_file


class DailyBetResultForm(forms.ModelForm):
    games = forms.CharField(
        required=False,
        label='Jogos para o sorteio',
        widget=forms.Textarea(
            attrs={
                'rows': 4,
                'placeholder': (
                    'Um jogo por linha. Exemplo:\n'
                    '1,2,3,4,5,6,7,8,9,10,11,12,13,14,15'
                ),
            }
        ),
        help_text='Informe 15 dezenas únicas entre 1 e 25 em cada linha. Opcional.',
    )
    confirm_games_change = forms.BooleanField(
        required=False,
        label='Confirmo a alteração dos jogos',
        help_text=(
            'Alterar as dezenas pode invalidar uma conferência ou prêmio já registrado.'
        ),
    )

    play_date = forms.DateField(
        label='Data do jogo',
        input_formats=['%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        help_text='Selecione a data no calendário.',
    )

    class Meta:
        model = DailyBetResult
        fields = ['play_date', 'concurso', 'invested_amount', 'returned_amount', 'notes']
        labels = {
            'concurso': 'Concurso (opcional)',
            'invested_amount': 'Valor investido (R$)',
            'returned_amount': 'Valor retornado (R$)',
            'notes': 'Observação',
        }
        widgets = {
            'invested_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'returned_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {'notes': 'Opcional.'}

    def add_game_received_fields(self, games):
        for game in games:
            field_name = f'game_{game.pk}_prize_received'
            self.fields[field_name] = forms.TypedChoiceField(
                label='Recebido',
                choices=[('0', 'Não'), ('1', 'Sim')],
                required=False,
                coerce=lambda value: value == '1' or value is True,
                initial='1' if game.prize_received else '0',
            )
            game.received_form_field = self[field_name]

    def clean_play_date(self):
        play_date = self.cleaned_data['play_date']
        queryset = DailyBetResult.active_objects.active().filter(play_date=play_date)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError('Já existe um registro para esta data.')
        return play_date

    def clean_games(self):
        raw_games = self.cleaned_data.get('games', '')
        games = []
        for line_number, line in enumerate(raw_games.splitlines(), start=1):
            values = [value.strip() for value in line.split(',') if value.strip()]
            if not values:
                continue
            try:
                games.append(validate_numbers(values))
            except InvalidGameError as exc:
                raise forms.ValidationError(
                    f'Jogo na linha {line_number}: {exc}'
                )
        return games


class ManualGameForm(forms.ModelForm):
    dezenas = forms.CharField(
        label='Dezenas apostadas (15 números, separados por vírgula)',
        widget=forms.TextInput(
            attrs={'placeholder': 'ex: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15'}
        ),
    )
    matched_numbers = forms.CharField(
        label='Dezenas acertadas (opcional, separadas por vírgula)',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'ex: 1,2,3'}),
    )

    class Meta:
        model = ConfirmedGame
        fields = [
            'dezenas',
            'concurso',
            'is_checked',
            'is_contemplated',
            'hits_count',
            'matched_numbers',
            'prize_amount',
            'prize_received',
        ]
        labels = {
            'concurso': 'Concurso (opcional)',
            'is_checked': 'Já foi conferido',
            'is_contemplated': 'Contemplado (teve prêmio)',
            'hits_count': 'Quantidade de acertos (opcional)',
            'prize_amount': 'Valor do prêmio (opcional, R$)',
            'prize_received': 'Recebido',
        }
        widgets = {
            'hits_count': forms.NumberInput(attrs={'min': 0, 'max': 15}),
            'prize_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'prize_received': forms.Select(choices=[(False, 'Não'), (True, 'Sim')]),
        }

    def clean_dezenas(self):
        raw = self.cleaned_data['dezenas']
        values = [value.strip() for value in raw.split(',') if value.strip()]
        try:
            return validate_numbers(values)
        except InvalidGameError as exc:
            raise forms.ValidationError(str(exc))

    def clean_matched_numbers(self):
        raw = self.cleaned_data.get('matched_numbers')
        if not raw:
            return None
        values = [value.strip() for value in raw.split(',') if value.strip()]
        try:
            parsed = [int(value) for value in values]
        except ValueError:
            raise forms.ValidationError('Dezenas acertadas devem ser números.')
        for value in parsed:
            if not (1 <= value <= 25):
                raise forms.ValidationError(f'Dezena fora do intervalo (1-25): {value}')
        return sorted(parsed)

    def clean(self):
        cleaned_data = super().clean()
        dezenas = cleaned_data.get('dezenas')
        matched_numbers = cleaned_data.get('matched_numbers')
        if matched_numbers and dezenas:
            invalid = set(matched_numbers) - set(dezenas)
            if invalid:
                raise forms.ValidationError(
                    f'Dezenas acertadas devem estar entre as dezenas apostadas: {sorted(invalid)}'
                )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.amount:
            instance.amount = settings.AI_BET_UNIT_PRICE
        if commit:
            instance.save()
        return instance
