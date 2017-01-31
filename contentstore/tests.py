import json
from datetime import datetime

import pytz

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from .models import Schedule, MessageSet, Message


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

    def make_messageset(self, short_name='messageset_one', notes=None,
                        next_set=None, schedule=None):
        if schedule is None:
            schedule = self.make_schedule()
        messageset_data = {
            'short_name': short_name,
            'notes': notes,
            'next_set': next_set,
            'default_schedule': schedule
        }
        return MessageSet.objects.create(**messageset_data)

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
    def test_read_messageset(self):
        # Setup
        schedule = self.make_schedule()
        messageset = self.make_messageset(schedule=schedule)
        # Execute
        response = self.client.get('/api/v1/messageset/%s/' % messageset.id,
                                   content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        d = MessageSet.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(d.short_name, 'messageset_one')
        self.assertEqual(d.notes, None)
        self.assertEqual(d.next_set, None)
        self.assertEqual(d.default_schedule, schedule)
        self.assertEqual(d.content_type, 'text')

    def test_create_messageset(self):
        # Setup
        schedule = self.make_schedule()
        messageset_data = {
            'short_name': 'messageset_one_but_very_longname_and_cool_yeah',
            'notes': None,
            'next_set': None,
            'default_schedule': schedule.id
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
        self.assertEqual(d.default_schedule, schedule)
        self.assertEqual(d.content_type, 'text')

    def test_list_messagesets(self):
        # Setup
        self.make_messageset()
        self.make_messageset(short_name='messageset_two')
        # Execute
        response = self.client.get('/api/v1/messageset/',
                                   content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["results"][0]["short_name"],
                         "messageset_one")
        self.assertEqual(response.data["results"][1]["short_name"],
                         "messageset_two")

    def test_filter_messagesets(self):
        # Setup
        self.make_messageset()
        self.make_messageset(short_name='messageset_two')
        # Execute
        response = self.client.get('/api/v1/messageset/',
                                   {'short_name': 'messageset_two'},
                                   content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["short_name"],
                         "messageset_two")

    def test_create_message(self):
        """
        A POST request should create a message object for a messageset.
        """
        messageset = self.make_messageset()

        data = {
            'messageset': messageset.pk,
            'sequence_number': 1,
            'lang': 'en',
            'text_content': 'Foo',
        }

        self.client.post(
            reverse('message-list'), json.dumps(data),
            content_type='application/json')

        [msg] = Message.objects.all()
        self.assertEqual(msg.messageset, messageset)
        self.assertEqual(msg.sequence_number, 1)
        self.assertEqual(msg.lang, 'en')
        self.assertEqual(msg.text_content, 'Foo')

    def test_create_message_constraint(self):
        """
        When creating a message, if creating a second message with matching
        messageset, sequence_number, and lang fields, it should not be
        created.
        """
        messageset = self.make_messageset()
        Message.objects.create(
            messageset=messageset, sequence_number=1, lang='en',
            text_content="Foo")

        data = {
            'messageset': messageset.pk,
            'sequence_number': 1,
            'lang': 'en',
            'text_content': 'Bar',
        }

        response = self.client.post(
            reverse('message-list'), json.dumps(data),
            content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {
            'non_field_errors': [
                "The fields messageset, sequence_number, lang must make a "
                "unique set."]
        })
        self.assertEqual(Message.objects.all().count(), 1)


class TestSchedule(TestCase):

    def test_cron_string(self):
        schedule = Schedule(
            minute='*',
            hour='*',
            day_of_week='1',
            day_of_month='1',
            month_of_year='*'
        )
        self.assertEqual(schedule.cron_string, '* * 1 * 1')

        schedule = Schedule(
            minute='0',
            hour='8',
            day_of_week='1, 2, 3',
            day_of_month='*',
            month_of_year='*'
        )
        self.assertEqual(schedule.cron_string, '0 8 * * 1,2,3')

        schedule = Schedule(
            minute='1',
            hour='2',
            day_of_week='3',
            day_of_month='4',
            month_of_year='5'
        )
        self.assertEqual(schedule.cron_string, '1 2 4 5 3')

    def test_get_run_times_between(self):
        start = datetime(2016, 11, 1, 0, 0, tzinfo=pytz.UTC)
        end = datetime(2016, 11, 30, 23, 59, tzinfo=pytz.UTC)

        # test with every mon, tues, wed in November 2016
        schedule = Schedule(day_of_week='1,2,3', hour='8', minute='0')
        runs = schedule.get_run_times_between(start, end)
        self.assertEqual(len(runs), 14)

        # test with every week day in November
        schedule = Schedule(day_of_week='1,2,3,4,5', hour='8', minute='0')
        runs = schedule.get_run_times_between(start, end)
        self.assertEqual(len(runs), 22)

        # test with every day in November
        schedule = Schedule(day_of_week='*', hour='8', minute='0')
        runs = schedule.get_run_times_between(start, end)
        self.assertEqual(len(runs), 30)

        # test with specific day in November
        schedule = Schedule(day_of_month='21', hour='8', minute='0')
        runs = schedule.get_run_times_between(start, end)
        self.assertEqual(len(runs), 1)
