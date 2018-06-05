from django.db.models.signals import post_delete, post_save
from django.test import TestCase

from .utils import normalise_metric_name
from contentstore.signals import schedule_deleted, schedule_saved
from contentstore.models import Schedule
from subscriptions.models import (
    Subscription, fire_metrics_if_new,
)


class NormaliseMetricNameTest(TestCase):
    def test_normalise_metric_name(self):
        """
        The normalise_metric_name function should replace all non-alphanumeric
        with underscores.
        """
        self.assertEqual(normalise_metric_name('foo^& bar'), 'foo_bar')
        self.assertEqual(normalise_metric_name('foo   bar'), 'foo_bar')
        self.assertEqual(normalise_metric_name('_foo!bar,'), 'foo_bar')


post_save_signals = (
    (fire_metrics_if_new, Subscription),
    (schedule_saved, Schedule),
)


post_delete_signals = (
    (schedule_deleted, Schedule),
)


def disable_signals():
    for (signal, model) in post_save_signals:
        post_save.disconnect(signal, sender=model)
    for (signal, model) in post_delete_signals:
        post_delete.disconnect(signal, sender=model)


def enable_signals():
    for (signal, model) in post_save_signals:
        post_save.connect(signal, sender=model)
    for (signal, model) in post_delete_signals:
        post_delete.connect(signal, sender=model)
