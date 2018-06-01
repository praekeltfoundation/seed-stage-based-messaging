"""
Tests for the contentstore tasks
"""

from django.db.models.signals import post_save
from django.test import TestCase
from mock import patch

from subscriptions.models import (
    Subscription, fire_sub_action_if_new, fire_metrics_if_new)
from contentstore.models import Schedule, MessageSet
from contentstore.tasks import queue_subscription_send


class QueueSubscriptionSendTaskTests(TestCase):
    """
    Tests for the queue subscription send task
    """
    def setUp(self):
        self.disable_signal_hooks()

    def tearDown(self):
        self.enable_signal_hooks()

    def disable_signal_hooks(self):
        """
        Remove the signal hooks
        """
        post_save.disconnect(fire_sub_action_if_new, sender=Subscription)
        post_save.disconnect(fire_metrics_if_new, sender=Subscription)

    def enable_signal_hooks(self):
        """
        Replace the disabled signal hooks
        """
        post_save.connect(fire_sub_action_if_new, sender=Subscription)
        post_save.connect(fire_metrics_if_new, sender=Subscription)

    @patch('contentstore.tasks.send_next_message')
    def test_queue_subscription_send(self, send_next_message):
        """
        The queue subscription send task should run the send next message task
        for each active and valid subscription for the specified schedule.
        """
        schedule1 = Schedule.objects.create()
        schedule2 = Schedule.objects.create()
        messageset = MessageSet.objects.create(default_schedule=schedule2)

        # Subscriptions that shouldn't be run
        Subscription.objects.create(messageset=messageset, schedule=schedule2)
        Subscription.objects.create(
            messageset=messageset, schedule=schedule1, active=False)
        Subscription.objects.create(
            messageset=messageset, schedule=schedule1, completed=True)
        Subscription.objects.create(
            messageset=messageset, schedule=schedule1, process_status=1)

        # Subscriptions that should be run
        subscription = Subscription.objects.create(
            messageset=messageset, schedule=schedule1)

        queue_subscription_send(str(schedule1.id))
        send_next_message.delay.assert_called_once_with(str(subscription.id))
