from contextlib import contextmanager
from unittest.mock import patch

from django.db.models import signals
from django.test import TestCase

from contentstore.models import Schedule, MessageSet
from contentstore.signals import schedule_saved
from subscriptions.models import Subscription, fire_metrics_if_new
from subscriptions.tasks import (
    calculate_subscription_lifecycle, find_behind_subscriptions)


@contextmanager
def disable_signal(signal_name, signal_fn, sender):
    signal = getattr(signals, signal_name)
    signal.disconnect(signal_fn, sender)
    try:
        yield None
    finally:
        signal.connect(signal_fn, sender)


class TestFindBehindSubscriptionsTask(TestCase):
    def test_find_behind_subscriptions_queues_tasks(self):
        """
        find_behind_subscriptions should queue processing for all the
        subscriptions that are active
        """
        with disable_signal('post_save', schedule_saved, Schedule):
            schedule = Schedule.objects.create()
        messageset = MessageSet.objects.create(default_schedule=schedule)
        with disable_signal('post_save', fire_metrics_if_new, Subscription):
            sub_valid = Subscription.objects.create(
                schedule=schedule, messageset=messageset)
            Subscription.objects.create(
                schedule=schedule, messageset=messageset, active=False)
            Subscription.objects.create(
                schedule=schedule, messageset=messageset, completed=True)
            Subscription.objects.create(
                schedule=schedule, messageset=messageset, process_status=-1)

        with patch.object(calculate_subscription_lifecycle, "delay") as p:
            find_behind_subscriptions.delay()
        p.assert_called_once_with(str(sub_valid.id))
