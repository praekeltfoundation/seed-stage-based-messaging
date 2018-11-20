from __future__ import absolute_import

import os

import celery
import raven
from raven.contrib.celery import register_signal, register_logger_signal

from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      'seed_stage_based_messaging.settings')


class Celery(celery.Celery):

    def on_configure(self):
        client = raven.Client(settings.STAGE_BASED_MESSAGING_SENTRY_DSN)

        # register a custom filter to filter out duplicate logs
        register_logger_signal(client)

        # hook into the Celery error handler
        register_signal(client)


app = Celery(__name__)

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))
