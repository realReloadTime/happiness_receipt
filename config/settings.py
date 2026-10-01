"""
Настройки проекта «Чек на удачу».

Все чувствительные и конфигурируемые значения (включая даты промо-акции)
читаются из .env (см. .env.example). В коде ничего не зашито.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


# --- Основные настройки Django ------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-only-not-for-production")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "receipts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "receipts.context_processors.campaign_period",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- База данных ---------------------------------------------------------------
# По умолчанию PostgreSQL (в Docker). Для локального быстрого запуска
# без Postgres можно выставить DB_ENGINE=sqlite в .env.
if os.getenv("DB_ENGINE", "postgres") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "happiness_receipt"),
            "USER": os.getenv("DB_USER", "happiness"),
            "PASSWORD": os.getenv("DB_PASSWORD", "happiness"),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Локализация ----------------------------------------------------------------
LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "ru")
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# --- Статика и медиа -------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

if not DEBUG:
    STORAGES = {
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Аутентификация ----------------------------------------------------------------
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "receipts:cabinet"
LOGOUT_REDIRECT_URL = "login"

# --- Промо-акция «Чек на удачу» -----------------------------------------------------
# Даты задаются в .env как обычные календарные даты в часовом поясе акции.
PROMO_START_DATE = os.getenv("PROMO_START_DATE", "2026-10-01")
PROMO_END_DATE = os.getenv("PROMO_END_DATE", "2026-10-31")
PROMO_TIMEZONE = os.getenv("PROMO_TIMEZONE", "Europe/Moscow")
# Количество победителей розыгрыша (выбираются автоматически из принятых чеков)
PROMO_WINNERS_COUNT = int(os.getenv("PROMO_WINNERS_COUNT", "3"))

# Максимальный размер фото чека (МБ) — бонусная фича
RECEIPT_PHOTO_MAX_MB = float(os.getenv("RECEIPT_PHOTO_MAX_MB", "10"))

# --- Django REST Framework ---------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PAGINATION_CLASS": "receipts.pagination.ReceiptPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}