from django import forms
from django.conf import settings

from .models import DailyBetResult


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

    def clean_play_date(self):
        play_date = self.cleaned_data['play_date']
        queryset = DailyBetResult.active_objects.active().filter(play_date=play_date)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError('Já existe um registro para esta data.')
        return play_date
