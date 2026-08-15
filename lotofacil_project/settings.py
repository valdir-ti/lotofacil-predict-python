"""Django settings for lotofacil_project project."""

import os
from decimal import Decimal
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_list(name, default=''):
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


DEBUG = env_bool('DEBUG', default=False)

SECRET_KEY = os.getenv('SECRET_KEY', '').strip()
insecure_secret_keys = {
    '',
    'change-me-to-a-long-random-value',
    'django-insecure-dev-only-change-me',
}
if not DEBUG and (
    SECRET_KEY in insecure_secret_keys or SECRET_KEY.startswith('django-insecure-')
):
    raise ImproperlyConfigured(
        'SECRET_KEY must be set to a strong, unique value when DEBUG=False.'
    )
if not SECRET_KEY:
    SECRET_KEY = 'django-insecure-dev-only-change-me'

configured_hosts = env_list('ALLOWED_HOSTS')
render_hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME', '').strip()
if render_hostname and render_hostname not in configured_hosts:
    configured_hosts.append(render_hostname)
if not DEBUG and not configured_hosts:
    raise ImproperlyConfigured(
        'ALLOWED_HOSTS must be configured when DEBUG=False.'
    )
ALLOWED_HOSTS = configured_hosts or ['localhost', '127.0.0.1']
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'analyzer',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'lotofacil_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'lotofacil_project.wsgi.application'


DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    database_options = {'conn_max_age': 600}
    if DATABASE_URL.startswith(('postgres://', 'postgresql://')):
        database_options['ssl_require'] = True
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            **database_options,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


STATIC_URL = '/static/'
STATICFILES_DIRS = []
project_static_dir = BASE_DIR / 'static'
if project_static_dir.exists():
    STATICFILES_DIRS.append(project_static_dir)
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication is intentionally Google-only. Local Django users remain
# available for the admin, while application routes will require a session.
SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]
LOGIN_URL = '/accounts/google/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*']
ACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_ONLY = True
ACCOUNT_ADAPTER = 'analyzer.adapters.AccountAdapter'
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID', ''),
            'secret': os.getenv('GOOGLE_CLIENT_SECRET', ''),
            'key': '',
        },
        'SCOPE': ['profile', 'email'],
    },
}

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', default=not DEBUG)
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', default=not DEBUG)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', default=not DEBUG)
SESSION_COOKIE_HTTPONLY = env_bool('SESSION_COOKIE_HTTPONLY', default=True)
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000' if not DEBUG else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    'SECURE_HSTS_INCLUDE_SUBDOMAINS', default=not DEBUG
)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = os.getenv('SECURE_REFERRER_POLICY', 'same-origin')
X_FRAME_OPTIONS = 'DENY'

# OpenAI configuration for lottery predictions.
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openai').strip().lower()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5.4-nano')
LLM_MAX_DRAWS = int(os.getenv('LLM_MAX_DRAWS', '500'))
LLM_GAME_COUNT = int(os.getenv('LLM_GAME_COUNT', '3'))
MAX_CONFIRMATION_GAMES = int(os.getenv('MAX_CONFIRMATION_GAMES', '20'))

# Valor unitario da aposta da Lotofacil, usado para calcular o valor investido
# quando um jogo gerado pela IA e confirmado.
AI_BET_UNIT_PRICE = Decimal(os.getenv('AI_BET_UNIT_PRICE', '3.50'))
