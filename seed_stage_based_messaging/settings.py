"""
Django settings for seed_stage_based_messaging project.

For more information on this file, see
https://docs.djangoproject.com/en/1.9/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.9/ref/settings/
"""

import os
import djcelery
import dj_database_url
import django_cache_url
import mimetypes

from kombu import Exchange, Queue

# Support SVG on admin
mimetypes.add_type("image/svg+xml", ".svg", True)
mimetypes.add_type("image/svg+xml", ".svgz", True)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.9/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'REPLACEME')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', False)

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = (
    # admin
    'django.contrib.admin',
    # core
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    # documentation
    'rest_framework_docs',
    # 3rd party
    'djcelery',
    'raven.contrib.django.raven_compat',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    # us
    'contentstore',
    'subscriptions',

)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

SITE_ID = 1
USE_SSL = os.environ.get('USE_SSL', 'false').lower() == 'true'

ROOT_URLCONF = 'seed_stage_based_messaging.urls'

WSGI_APPLICATION = 'seed_stage_based_messaging.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get(
            'STAGE_BASED_MESSAGING_DATABASE',
            'postgres://postgres:@localhost/seed_stage_based_messaging')),
}


# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/

LANGUAGE_CODE = 'en-gb'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django.contrib.staticfiles.finders.FileSystemFinder',
)

STATIC_ROOT = 'staticfiles'
STATIC_URL = '/static/'

MEDIA_ROOT = 'mediafiles'
MEDIA_URL = '/media/'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates')
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Sentry configuration
STAGE_BASED_MESSAGING_SENTRY_DSN = os.environ.get(
    'STAGE_BASED_MESSAGING_SENTRY_DSN', None)
RAVEN_CONFIG = {
    # DevOps will supply you with this.
    'dsn': STAGE_BASED_MESSAGING_SENTRY_DSN,
}

# REST Framework conf defaults
REST_FRAMEWORK = {
    'PAGE_SIZE': 1000,
    'DEFAULT_PAGINATION_CLASS':
        'rest_framework.pagination.CursorPagination',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': ('rest_framework.filters.DjangoFilterBackend',)
}

# Celery configuration options
CELERY_RESULT_BACKEND = 'djcelery.backends.database:DatabaseBackend'
CELERYBEAT_SCHEDULER = 'djcelery.schedulers.DatabaseScheduler'

BROKER_URL = os.environ.get(
    'BROKER_URL',
    'amqp://localhost:5672//seed_stage_based_messaging')

CELERY_DEFAULT_QUEUE = 'seed_stage_based_messaging'
CELERY_QUEUES = (
    Queue('seed_stage_based_messaging',
          Exchange('seed_stage_based_messaging'),
          routing_key='seed_stage_based_messaging'),
)

CELERY_ALWAYS_EAGER = False

# Tell Celery where to find the tasks
CELERY_IMPORTS = (
    'subscriptions.tasks',
    'contentstore.tasks'
)

CELERY_CREATE_MISSING_QUEUES = True
CELERY_ROUTES = {
    'celery.backend_cleanup': {
        'queue': 'mediumpriority',
    },
    'subscriptions.tasks.send_next_message': {
        'queue': 'priority',
    },
    'subscriptions.tasks.post_send_process': {
        'queue': 'mediumpriority',
    },
    'subscriptions.tasks.schedule_create': {
        'queue': 'mediumpriority',
    },
    'subscriptions.tasks.schedule_disable': {
        'queue': 'mediumpriority',
    },
    'subscriptions.tasks.requeue_failed_tasks': {
        'queue': 'mediumpriority',
    },
    'subscriptions.tasks.fire_metric': {
        'queue': 'metrics',
    },
    'subscriptions.tasks.scheduled_metrics': {
        'queue': 'metrics',
    },
    'subscriptions.tasks.fire_active_last': {
        'queue': 'metrics',
    },
    'subscriptions.tasks.fire_created_last': {
        'queue': 'metrics',
    },
    'subscriptions.tasks.fire_broken_last': {
        'queue': 'metrics',
    },
    'subscriptions.tasks.fire_completed_last': {
        'queue': 'metrics',
    },
    'subscriptions.tasks.fire_incomplete_last': {
        'queue': 'metrics',
    },
}

CELERYD_MAX_TASKS_PER_CHILD = 50

CACHE_URL = os.environ.get('STAGE_BASED_MESSAGING_CACHE', 'locmem://')
CACHES = {
    'default': django_cache_url.parse(CACHE_URL),
}

METRICS_REALTIME = [
    'subscriptions.created.sum',
    'subscriptions.send_next_message_errored.sum'
]
# Note metrics with variable names of messageset short_names not included here
METRICS_SCHEDULED = [
    'subscriptions.active.last',
    'subscriptions.created.last',
    'subscriptions.broken.last',
    'subscriptions.completed.last',
    'subscriptions.send.estimate.0.last',
    'subscriptions.send.estimate.1.last',
    'subscriptions.send.estimate.2.last',
    'subscriptions.send.estimate.3.last',
    'subscriptions.send.estimate.4.last',
    'subscriptions.send.estimate.5.last',
    'subscriptions.send.estimate.6.last',
    'subscriptions.send_next_message.connection_error.sum',
    'subscriptions.send_next_message.http_error.400.sum',
    'subscriptions.send_next_message.http_error.401.sum',
    'subscriptions.send_next_message.http_error.403.sum',
    'subscriptions.send_next_message.http_error.404.sum',
    'subscriptions.send_next_message.http_error.500.sum',
    'subscriptions.send_next_message.timeout.sum',
]
METRICS_SCHEDULED_TASKS = [
    'fire_active_last',
    'fire_created_last',
    'fire_broken_last',
    'fire_completed_last',
    'fire_incomplete_last',
    'fire_messagesets_tasks',
    'fire_week_estimate_last'
]

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_IGNORE_RESULT = True

djcelery.setup_loader()

STAGE_BASED_MESSAGING_URL = os.environ.get("STAGE_BASED_MESSAGING_URL", None)

SCHEDULER_URL = os.environ.get("SCHEDULER_URL", None)
SCHEDULER_API_TOKEN = os.environ.get("SCHEDULER_API_TOKEN", "REPLACEME")
SCHEDULER_INBOUND_API_TOKEN = \
    os.environ.get("SCHEDULER_INBOUND_API_TOKEN", "REPLACEMEONLOAD")

IDENTITY_STORE_URL = os.environ.get("IDENTITY_STORE_URL", None)
IDENTITY_STORE_TOKEN = os.environ.get("IDENTITY_STORE_TOKEN", "REPLACEME")

MESSAGE_SENDER_URL = os.environ.get("MESSAGE_SENDER_URL", None)
MESSAGE_SENDER_TOKEN = os.environ.get("MESSAGE_SENDER_TOKEN", "REPLACEME")

METRICS_URL = os.environ.get("METRICS_URL", None)
METRICS_AUTH = (
    os.environ.get("METRICS_AUTH_USER", "REPLACEME"),
    os.environ.get("METRICS_AUTH_PASSWORD", "REPLACEME"),
)

DEFAULT_REQUEST_TIMEOUT = float(os.environ.get("DEFAULT_REQUEST_TIMEOUT", 30))

AUDIO_FTP_HOST = os.environ.get('AUDIO_FTP_HOST')
AUDIO_FTP_PORT = os.environ.get('AUDIO_FTP_PORT')
AUDIO_FTP_USER = os.environ.get('AUDIO_FTP_USER')
AUDIO_FTP_PASS = os.environ.get('AUDIO_FTP_PASS')
AUDIO_FTP_ROOT = os.environ.get('AUDIO_FTP_ROOT')

DRY_RUN_MESSAGESETS = map(int, filter(bool, os.environ.get(
    'DRY_RUN_MESSAGESETS', '').split(',')))
