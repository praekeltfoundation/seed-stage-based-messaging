import json

from django.test import TestCase
from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from .models import Schedule, MessageSet


class APITestCase(TestCase):

    def setUp(self):
        self.client = APIClient()


class AuthenticatedAPITestCase(APITestCase):

    def make_schedule(self):
        # Create hourly schedule
        schedule_data = {
            'hour': 1
        }
        return Schedule.objects.create(**schedule_data)

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


class TestContentStoreApi(AuthenticatedAPITestCase):

    # Schedule testing
    def test_read_schedule(self):
        # Setup
        existing = self.make_schedule()
        # Execute
        response = self.client.get('/api/v1/schedule/%s/' % existing.id,
                                   content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['hour'], '1')
        d = Schedule.objects.last()
        self.assertEqual(d.cron_string, '* 1 * * *')

    def test_filter_schedule(self):
        # Setup
        existing = self.make_schedule()
        # Execute
        response = self.client.get('/api/v1/schedule/',
                                   {'cron_string':  '* 1 * * *'},
                                   content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['id'], existing.id)

    # MessageSet testing
    def test_create_messageset(self):
        # Setup
        existing_schedule = self.make_schedule()
        messageset_data = {
            'short_name': 'messageset_one_but_very_longname_and_cool_yeah',
            'notes': None,
            'next_set': None,
            'default_schedule': existing_schedule.id
        }
        # Execute
        response = self.client.post('/api/v1/messageset/',
                                    json.dumps(messageset_data),
                                    content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        d = MessageSet.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(d.short_name,
                         'messageset_one_but_very_longname_and_cool_yeah')
        self.assertEqual(d.notes, None)
        self.assertEqual(d.next_set, None)
        self.assertEqual(d.default_schedule, existing_schedule)
        self.assertEqual(d.content_type, 'text')
