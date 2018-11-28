from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

from django.db.models import signals
from django.test import TestCase

from contentstore.models import Schedule, MessageSet, Message
from contentstore.signals import schedule_saved
from subscriptions.models import (
    BehindSubscription, Subscription, fire_metrics_if_new)
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


class TestCalculateSubscriptionLifecycle(TestCase):
    def test_calculate_subscription_lifecycle_correct(self):
        """
        If the subscription is in the correct place, then no
        BehindSubscriptions should be created
        """
        with disable_signal('post_save', schedule_saved, Schedule):
            schedule = Schedule.objects.create()
        messageset = MessageSet.objects.create(default_schedule=schedule)
        for i in range(10):
            Message.objects.create(
                messageset=messageset, text_content=str(i), sequence_number=i)
        with disable_signal('post_save', fire_metrics_if_new, Subscription):
            subscription = Subscription.objects.create(
                schedule=schedule, messageset=messageset)

        # Ensure that we make the minumum amount of requests needed
        # 1: Get the subscription with related schedule and messageset
        # 2: Get the count of messages for the messageset
        with self.assertNumQueries(2):
            calculate_subscription_lifecycle.delay(str(subscription.id))
        self.assertEqual(BehindSubscription.objects.count(), 0)

    def test_calculate_subscription_lifecycle_behind(self):
        """
        If the subscription is behind, then a BehindSubscription should be
        created with the correct details
        """
        with disable_signal('post_save', schedule_saved, Schedule):
            schedule = Schedule.objects.create(minute=0)
        messageset = MessageSet.objects.create(default_schedule=schedule)
        for i in range(10):
            Message.objects.create(
                messageset=messageset, text_content=str(i), sequence_number=i)
        with disable_signal('post_save', fire_metrics_if_new, Subscription):
            subscription = Subscription.objects.create(
                schedule=schedule, messageset=messageset)
            subscription.created_at = datetime.now() - timedelta(hours=2)
            subscription.save()

        calculate_subscription_lifecycle.delay(str(subscription.id))
        [behind] = BehindSubscription.objects.all()
        self.assertEqual(behind.subscription, subscription)
        self.assertEqual(behind.messages_behind, 2)
        self.assertEqual(behind.current_messageset, subscription.messageset)
        self.assertEqual(
            behind.current_sequence_number, subscription.next_sequence_number)
        self.assertEqual(behind.expected_messageset, subscription.messageset)
        self.assertEqual(behind.expected_sequence_number, 3)
