from seed_stage_based_messaging.settings import *  # flake8: noqa

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'TESTSEKRET'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
CELERY_ALWAYS_EAGER = True
BROKER_BACKEND = 'memory'
CELERY_RESULT_BACKEND = 'djcelery.backends.database:DatabaseBackend'

SCHEDULER_URL = "http://seed-scheduler/api/v1"
SCHEDULER_API_TOKEN = "REPLACEME"

IDENTITY_STORE_URL = "http://seed-identity-store/api/v1"
IDENTITY_STORE_TOKEN = "REPLACEME"

MESSAGE_SENDER_URL = "http://seed-message-sender/api/v1"
MESSAGE_SENDER_TOKEN = "REPLACEME"

METRICS_URL = "http://metrics-url"
METRICS_AUTH_TOKEN = "REPLACEME"

PASSWORD_HASHERS = ('django.contrib.auth.hashers.MD5PasswordHasher',)


# REST Framework conf defaults
REST_FRAMEWORK['PAGE_SIZE'] = 2

AUDIO_FTP_HOST = 'localhost'
AUDIO_FTP_PORT = '2222'
AUDIO_FTP_USER = 'test'
AUDIO_FTP_PASS = 'secret'
AUDIO_FTP_ROOT = 'test_directory'
