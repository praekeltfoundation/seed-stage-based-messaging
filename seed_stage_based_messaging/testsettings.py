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

SCHEDULER_URL = os.environ.get("SCHEDULER_URL",
    "http://seed-scheduler/api/v1")
SCHEDULER_API_TOKEN = os.environ.get("SCHEDULER_API_TOKEN", "REPLACEME")
