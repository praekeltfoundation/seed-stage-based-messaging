import responses
import json

from django.contrib.auth.models import User
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from .models import Subscription


class APITestCase(TestCase):

    def setUp(self):
        self.client = APIClient()


class AuthenticatedAPITestCase(APITestCase):

    def setUp(self):
        super(AuthenticatedAPITestCase, self).setUp()
        self.username = 'testuser'
        self.password = 'testpass'
        self.user = User.objects.create_user(self.username,
                                             'testuser@example.com',
                                             self.password)
        token = Token.objects.create(user=self.user)
        self.token = token.key
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)


class TestLogin(AuthenticatedAPITestCase):

    def test_login(self):
        # Setup
        post_auth = {"username": "testuser",
                     "password": "testpass"}
        # Execute
        request = self.client.post(
            '/api/token-auth/', post_auth)
        token = request.data.get('token', None)
        # Check
        self.assertIsNotNone(
            token, "Could not receive authentication token on login post.")
        self.assertEqual(
            request.status_code, 200,
            "Status code on /api/token-auth was %s (should be 200)."
            % request.status_code)


class TestSubscriptionsAPI(AuthenticatedAPITestCase):

    @responses.activate
    def test_create_subscription_data(self):

        schedule = {
            "class": "mama.ng.scheduler.Schedule",
            "id": "1",
            "cronDefinition": "1 2 3 4 5",
            "dateCreated": "2015-04-05T21:59:28Z",
            "endpoint": "http://examplecontrol.com/api/v1",
            "frequency": 10,
            "messages": None,
            "nextSend": "2015-04-05T22:00:00Z",
            "sendCounter": 0,
            "subscriptionId": "1234"
        }

        responses.add(
            responses.GET,
            "http://127.0.0.1:8000/mama-ng-scheduler/rest/schedules",
            json.dumps(schedule),
            status=200, content_type='application/json')

        post_subscription = {
            "contact": "/api/v1/contacts/%s/" % self.contact,
            "messageset_id": "1",
            "next_sequence_number": "1",
            "lang": "en_ZA",
            "active": "true",
            "completed": "false",
            "schedule": "1",
            "process_status": "0",
            "metadata": {
                "source": "RapidProVoice"
            }
        }
        response = self.client.post('/api/v1/subscriptions/',
                                    json.dumps(post_subscription),
                                    content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Subscription.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(d.version, 1)
        self.assertEqual(d.messageset_id, 1)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "en_ZA")
        self.assertEqual(d.active, True)
        self.assertEqual(d.completed, False)
        self.assertEqual(d.schedule, 1)
        self.assertEqual(d.process_status, 0)
        self.assertEqual(d.metadata["source"], "RapidProVoice")
