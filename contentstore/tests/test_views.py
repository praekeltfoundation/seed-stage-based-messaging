"""
Tests for the contentstore views
"""

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from unittest.mock import patch

from contentstore.models import Schedule
from seed_stage_based_messaging import test_utils as utils


class ScheduleViewsetTests(APITestCase):
    """
    Tests for the schedule viewset
    """
    def setUp(self):
        utils.disable_signals()

    def tearDown(self):
        utils.enable_signals()

    @patch('contentstore.views.queue_subscription_send')
    def test_send_action(self, task):
        """
        The send action on the schedule detail should trigger the celery
        task for sending the subscriptions for that schedule
        """
        user = User.objects.create_user('test')
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        schedule = Schedule.objects.create()

        response = self.client.post(schedule.send_url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        task.delay.assert_called_once_with(str(schedule.id))
