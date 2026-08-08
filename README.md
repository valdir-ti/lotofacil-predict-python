# Lotofacil Prediction Python

Aplicacao web em Django para:

- analisar historico de concursos da Lotofacil a partir de arquivo Excel;
- calcular metricas estatisticas e gerar 3 jogos recomendados;
- controlar resultados financeiros diarios (investimento x retorno);
- exibir dados do proximo concurso via API publica da Caixa.

## Tecnologias

- Python 3.11+
- Django 6.0
- OpenPyXL
- SQLite (padrao local) ou PostgreSQL (via `DATABASE_URL`)
- WhiteNoise (arquivos estaticos)
- Gunicorn (producao)

Dependencias estao em [requirements.txt](requirements.txt).

## Funcionalidades

### 1) Analise por planilha Excel

Tela inicial permite upload de arquivo `.xlsx` com concursos da Lotofacil.

Formato esperado de colunas:

- `Concurso`
- `Data Sorteio` (opcional para as metricas, mas recomendado)
- `Bola1` ate `Bola15`

O parser:

- tenta localizar automaticamente o cabecalho;
- ignora linhas invalidas;
- valida dezenas unicas no intervalo 1-25;
- ordena concursos por numero/data quando possivel.

Implementacao principal em [analyzer/services/excel_parser.py](analyzer/services/excel_parser.py).

### 2) Dashboard de metricas

Com base nos concursos validos, calcula:

- dezenas mais e menos frequentes;
- dezenas atrasadas;
- médias de pares/ímpares, soma e repetição;
- distribuicao de padrões;
- 3 jogos recomendados com regras heuristicas.

Implementacao principal em [analyzer/services/metrics.py](analyzer/services/metrics.py).

### 2.1) Backtesting das heuristicas

O projeto possui um backtesting walk-forward que usa somente concursos anteriores ao concurso
testado e compara o gerador heuristico com dois baselines aleatorios:

```bash
python manage.py backtest_lotofacil caminho/para/lotofacil.xlsx --min-history 100 --game-count 3
```

O resultado JSON informa media, mediana, maximo e contagens de jogos com 11, 12, 13, 14 e 15
acertos para cada estrategia. As heuristicas sao rankings/composicoes estatisticas e nao alteram
a probabilidade matematica de uma dezena.

### 3) Controle financeiro diario

CRUD de registros financeiros com soft delete:

- listagem: `/financeiro/`
- novo registro: `/financeiro/novo/`
- edicao: `/financeiro/<id>/editar/`
- exclusao (desativacao): `/financeiro/<id>/excluir/`

Modelo principal em [analyzer/models.py](analyzer/models.py).

### 4) Proximo concurso (API Caixa)

A home consulta a API publica da Caixa para mostrar:

- numero do proximo concurso;
- data do proximo concurso;
- valor acumulado/estimado.

Implementacao em [analyzer/services/lotofacil_api.py](analyzer/services/lotofacil_api.py).

## Estrutura do projeto

```text
lotofacil-prediction-python/
├── analyzer/
│   ├── services/
│   │   ├── excel_parser.py
│   │   ├── lotofacil_api.py
│   │   └── metrics.py
│   ├── templates/analyzer/
│   ├── tests/
│   ├── models.py
│   ├── urls.py
│   └── views.py
├── lotofacil_project/
│   ├── settings.py
│   └── urls.py
├── manage.py
├── requirements.txt
├── Procfile
└── runtime.txt
```

## Como rodar localmente (Windows)

### 1) Pre-requisitos

- Python 3.11+ instalado
- Git (opcional)

### 2) Entrar na pasta do projeto

```bash
cd E:/projects/lotofacil-prediction-python
```

### 3) Criar e ativar ambiente virtual

Se ainda nao existir `.venv`:

```bash
python -m venv .venv
```

Ativar no Git Bash:

```bash
source .venv/Scripts/activate
```

### 4) Instalar dependencias

```bash
pip install -r requirements.txt
```

### 5) Configurar variaveis de ambiente

Copie [ .env.example ](.env.example) para `.env` e ajuste os valores necessarios:

```env
DEBUG=True
SECRET_KEY=django-insecure-dev-only-change-me
ALLOWED_HOSTS=localhost,127.0.0.1
```

Observacoes:

- Se `DATABASE_URL` nao for definido, o projeto usa SQLite local (`db.sqlite3`).
- Para PostgreSQL, defina `DATABASE_URL` no formato suportado pelo `dj-database-url`.

### 6) Rodar migracoes

```bash
python manage.py migrate
```

### 7) Iniciar servidor

```bash
python manage.py runserver
```

Acesse:

- Home: `http://127.0.0.1:8000/`
- Financeiro: `http://127.0.0.1:8000/financeiro/`

## Testes

Rodar toda a suite da app:

```bash
python manage.py test analyzer
```

Rodar testes especificos:

```bash
python manage.py test analyzer.tests.test_views analyzer.tests.test_metrics analyzer.tests.test_parser analyzer.tests.test_lotofacil_api
```

Se estiver usando PostgreSQL e houver conflito com banco de teste existente (`test_postgres`), limpe o estado do banco de teste ou rode apenas testes unitarios sem DB quando aplicavel.

## Comandos uteis

```bash
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

Painel admin: `http://127.0.0.1:8000/admin/`

## Deploy (resumo)

Arquivos ja preparados para deploy:

- [Procfile](Procfile) com Gunicorn
- [runtime.txt](runtime.txt)
- suporte a `DATABASE_URL` em [lotofacil_project/settings.py](lotofacil_project/settings.py)
- WhiteNoise para estaticos

Comando de web process:

```text
web: gunicorn lotofacil_project.wsgi:application --log-file -
```

## Licenca

Sem licenca definida atualmente. Adicione uma licenca (MIT, Apache-2.0 etc.) conforme a necessidade do projeto.
