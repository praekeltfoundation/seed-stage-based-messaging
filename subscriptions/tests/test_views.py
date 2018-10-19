from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from contentstore.models import Schedule, MessageSet
from subscriptions.models import Subscription
from seed_stage_based_messaging import test_utils as utils


class SubscriptionSendViewTests(APITestCase):
    def setUp(self):
        utils.disable_signals()

    def tearDown(self):
        utils.enable_signals()

    @patch('subscriptions.views.schedule_disable')
    def test_disables_schedule(self, disable_schedule):
        """
        The subscription send view should disable the schedule for the
        subscription
        """
        schedule = Schedule.objects.create()
        messageset = MessageSet.objects.create(default_schedule=schedule)
        subscription = Subscription.objects.create(
            schedule=schedule, messageset=messageset)
        url = reverse('subscription-send', args=[str(subscription.id)])

        user = User.objects.create_user('test')
        self.client.force_authenticate(user=user)

        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        disable_schedule.delay.assert_called_once_with(str(subscription.id))
