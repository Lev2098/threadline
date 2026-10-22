"""Django settings, configured entirely from environment variables (12-factor).

Every external service is optional: without POSTGRES_HOST the app falls back
to SQLite, without REDIS_URL to in-process cache, without ELASTICSEARCH_URL to
database search, without CELERY_BROKER_URL tasks run inline. The same code
therefore runs on a laptop, in tests and in the full docker compose stack.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG")
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-secret-key-change-me" if DEBUG else "")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "channels",
    "strawberry.django",
    "comments.adapters.outbound.persistence.apps.PersistenceConfig",
    "comments.adapters.inbound.cli.apps.CliConfig",
    "comments.adapters.inbound.web.apps.WebConfig",
]

MIDDLEWARE = [
    "config.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
# HTTP is served by gunicorn (WSGI, threads); only WebSockets go through ASGI.
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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
            ],
        },
    },
]

# --- Database -----------------------------------------------------------------

if env("POSTGRES_HOST"):

    def _pg(host: str) -> dict[str, object]:
        return {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": host,
            "PORT": env("POSTGRES_PORT", "5432"),
            "NAME": env("POSTGRES_DB", "comments"),
            "USER": env("POSTGRES_USER", "comments"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
            # Under ASGI every sync_to_async thread would keep its own persistent
            # connection (CONN_MAX_AGE), exhausting max_connections under load.
            # A bounded psycopg pool per process caps it: processes x POOL_MAX.
            "CONN_MAX_AGE": 0,
            "OPTIONS": {
                "connect_timeout": 5,
                "pool": {
                    "min_size": int(env("POSTGRES_POOL_MIN", "2")),
                    "max_size": int(env("POSTGRES_POOL_MAX", "10")),
                    "timeout": 10,
                },
            },
        }

    DATABASES = {"default": _pg(env("POSTGRES_HOST"))}
    if env("POSTGRES_REPLICA_HOST"):
        DATABASES["replica"] = _pg(env("POSTGRES_REPLICA_HOST"))
        DATABASE_ROUTERS = ["config.db_router.PrimaryReplicaRouter"]
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# INCLUDE columns of covering indexes are PostgreSQL-only; the SQLite dev
# fallback just ignores them, which is fine.
SILENCED_SYSTEM_CHECKS = ["models.W040"]

# --- Cache / Redis / Channels ---------------------------------------------------

REDIS_URL = env("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "comments",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 2,
                "SOCKET_TIMEOUT": 2,
                # Cache is an optimization: a Redis outage must not take reads down.
                "IGNORE_EXCEPTIONS": True,
            },
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [env("CHANNELS_REDIS_URL", REDIS_URL)]},
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

DJANGO_REDIS_IGNORE_EXCEPTIONS = True

# --- Celery (RabbitMQ broker) -----------------------------------------------------

CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_TASK_ALWAYS_EAGER = not CELERY_BROKER_URL
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_TASK_DEFAULT_QUEUE = "comments"
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_IGNORE_RESULT = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Publisher confirms: send_task returns only after RabbitMQ has persisted the
# message. A broker crash right after a 201 can no longer drop the event; if the
# broker doesn't confirm, the publisher's inline fallback handles it instead.
CELERY_BROKER_TRANSPORT_OPTIONS = {"confirm_publish": True, "max_retries": 2, "interval_start": 0, "interval_step": 0.5}
CELERY_TASK_PUBLISH_RETRY = False
CELERY_BROKER_CONNECTION_TIMEOUT = 2  # a down broker must not hold a request; the fallback takes over

# --- Search -----------------------------------------------------------------------

ELASTICSEARCH_URL = env("ELASTICSEARCH_URL")
ELASTICSEARCH_INDEX = env("ELASTICSEARCH_INDEX", "comments")

# --- Auth (anonymous JWT client sessions) ------------------------------------------

JWT_SECRET = env("JWT_SECRET", SECRET_KEY)
JWT_TTL_SECONDS = int(env("JWT_TTL_SECONDS", str(60 * 60 * 24 * 30)))
# Only trust X-Real-IP when a reverse proxy we control sets it.
TRUST_PROXY_HEADERS = env_bool("TRUST_PROXY_HEADERS")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["comments.adapters.inbound.rest.auth.JWTClientAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "session": env("THROTTLE_SESSION", "30/min"),
        "captcha": env("THROTTLE_CAPTCHA", "60/min"),
        "post": env("THROTTLE_POST", "20/min"),
        "preview": env("THROTTLE_PREVIEW", "120/min"),
        "read": env("THROTTLE_READ", "600/min"),
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "comments.adapters.inbound.rest.errors.exception_handler",
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "dZEN Comments API",
    "DESCRIPTION": "Threaded comments with captcha, attachments, live updates and search.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- Load testing ---------------------------------------------------------------------
# Never enable in production: makes every captcha accept LOADTEST_CAPTCHA_ANSWER.
LOADTEST_MODE = env_bool("LOADTEST_MODE")
LOADTEST_CAPTCHA_ANSWER = env("LOADTEST_CAPTCHA_ANSWER", "loadtest") if LOADTEST_MODE else ""
if LOADTEST_MODE:
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []

# --- SEO / server rendering ---------------------------------------------------------------
# Public origin used in canonical URLs, sitemaps and Open Graph tags.
SITE_URL = env("SITE_URL", "http://localhost:8080")
# Built SPA index.html (from the edge) used as the shell of server-rendered pages.
SPA_SHELL_URL = env("SPA_SHELL_URL")

# --- Files ----------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = env("STATIC_ROOT", str(BASE_DIR / "staticfiles"))
MEDIA_URL = env("MEDIA_URL", "/media/")
MEDIA_ROOT = env("MEDIA_ROOT", str(BASE_DIR / "media"))
DATA_UPLOAD_MAX_MEMORY_SIZE = 11 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 11 * 1024 * 1024

# --- Security headers -------------------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = env_bool("SECURE_COOKIES", not DEBUG)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
if env_bool("BEHIND_TLS_PROXY"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {"elastic_transport": {"level": "WARNING"}},
}
