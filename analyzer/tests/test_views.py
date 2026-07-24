from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook


def _excel_payload():
    workbook = Workbook()
    sheet = workbook.active
    headers = ['Concurso', 'Data Sorteio'] + [f'Bola{i}' for i in range(1, 16)]
    sheet.append(headers)
    sheet.append([1, '01/01/2024', *range(1, 16)])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.read()


class HomeViewTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Analise de Resultados da Lotofacil')

    def test_upload_excel_and_get_results(self):
        file_data = _excel_payload()
        uploaded = SimpleUploadedFile(
            'lotofacil.xlsx',
            file_data,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post('/', {'file': uploaded})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard de Resultados')
        self.assertContains(response, 'Todos os indicadores abaixo usam 100% dos concursos válidos')
        self.assertContains(response, '3 jogos recomendados')
