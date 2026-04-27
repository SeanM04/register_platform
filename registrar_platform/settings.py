import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def get_env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def get_env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def get_env_int(name, default=0):
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


DEBUG = get_env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-dev-key"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is False.")

ALLOWED_HOSTS = get_env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
CSRF_TRUSTED_ORIGINS = get_env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set when DJANGO_DEBUG is False.")


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'dashboard',
    'chatbot',
]

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "accounts.backends.LockoutBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_LOCKOUT_FAILURE_LIMIT = get_env_int("AUTH_LOCKOUT_FAILURE_LIMIT", 5)
AUTH_LOCKOUT_DURATION_MINUTES = get_env_int("AUTH_LOCKOUT_DURATION_MINUTES", 15)
LOGIN_BYPASS_DOMAINS = get_env_list("LOGIN_BYPASS_DOMAINS", "")

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.SessionValidationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'registrar_platform.urls'

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

WSGI_APPLICATION = 'registrar_platform.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'registrar_dashboard'),
        'USER': os.getenv('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
        'HOST': os.getenv('POSTGRES_HOST', '127.0.0.1'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = get_env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = get_env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = get_env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_SAMESITE = os.getenv("DJANGO_SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("DJANGO_CSRF_COOKIE_SAMESITE", "Lax")
SECURE_HSTS_SECONDS = get_env_int("DJANGO_SECURE_HSTS_SECONDS", 0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = get_env_bool("DJANGO_SECURE_HSTS_PRELOAD", not DEBUG)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# The demographics MapLibre view and other approved third-party assets need an
# origin referrer on cross-origin requests. This policy keeps same-origin URL
# detail while only sending the origin externally.
SECURE_REFERRER_POLICY = os.getenv("DJANGO_SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin")
X_FRAME_OPTIONS = os.getenv("DJANGO_X_FRAME_OPTIONS", "DENY")
AI_INSIGHTS_ENABLED = get_env_bool("AI_INSIGHTS_ENABLED", get_env_bool("OPENAI_INSIGHTS_ENABLED", False))
AI_INSIGHTS_PROVIDER = os.getenv("AI_INSIGHTS_PROVIDER", "auto").strip().lower()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("Google_API_KEY", "")
GOOGLE_INSIGHTS_MODEL = os.getenv("GOOGLE_INSIGHTS_MODEL", "gemini-2.5-flash-lite")
GOOGLE_INSIGHTS_TIMEOUT_SECONDS = get_env_int("GOOGLE_INSIGHTS_TIMEOUT_SECONDS", 6)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_INSIGHTS_ENABLED = get_env_bool("OPENAI_INSIGHTS_ENABLED", False)
OPENAI_INSIGHTS_MODEL = os.getenv("OPENAI_INSIGHTS_MODEL", "gpt-5.4-mini")
OPENAI_INSIGHTS_TIMEOUT_SECONDS = get_env_int("OPENAI_INSIGHTS_TIMEOUT_SECONDS", 6)
CHATBOT_ENABLED = get_env_bool("CHATBOT_ENABLED", True)
CHATBOT_PROVIDER = os.getenv("CHATBOT_PROVIDER", AI_INSIGHTS_PROVIDER or "auto").strip().lower()
CHATBOT_GOOGLE_MODEL = os.getenv("CHATBOT_GOOGLE_MODEL", GOOGLE_INSIGHTS_MODEL)
CHATBOT_OPENAI_MODEL = os.getenv("CHATBOT_OPENAI_MODEL", OPENAI_INSIGHTS_MODEL)
CHATBOT_TIMEOUT_SECONDS = get_env_int(
    "CHATBOT_TIMEOUT_SECONDS",
    max(GOOGLE_INSIGHTS_TIMEOUT_SECONDS, OPENAI_INSIGHTS_TIMEOUT_SECONDS, 12),
)

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "login"


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

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Johannesburg'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}
