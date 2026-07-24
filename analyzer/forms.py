from django import forms
from django.conf import settings


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
