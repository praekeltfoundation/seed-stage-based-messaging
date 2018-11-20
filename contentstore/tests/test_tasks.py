"""
Tests for the contentstore tasks
"""

from django.test import TestCase
from unittest.mock import patch

from subscriptions.models import Subscription
from contentstore.models import Schedule, MessageSet
from contentstore.tasks import queue_subscription_send
from seed_stage_based_messaging import test_utils as utils


class QueueSubscriptionSendTaskTests(TestCase):
    """
    Tests for the queue subscription send task
    """
    def setUp(self):
        utils.disable_signals()

    def tearDown(self):
        utils.enable_signals()

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
