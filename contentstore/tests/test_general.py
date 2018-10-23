import json
from datetime import datetime
from unittest.mock import patch
import os

import pytz
import responses

from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from ..models import Schedule, MessageSet, Message, BinaryContent
from seed_stage_based_messaging import test_utils as utils


class APITestCase(TestCase):

    def setUp(self):
        self.client = APIClient()
        utils.disable_signals()

    def tearDown(self):
        utils.enable_signals()


class MessageSetTestMixin():
    def make_schedule(self):
        # Create hourly schedule
        schedule_data = {
            'minute': '0',
        }
        return Schedule.objects.create(**schedule_data)

    def make_messageset(self, short_name='messageset_one', notes=None,
                        next_set=None, schedule=None, channel=None):
        if schedule is None:
            schedule = self.make_schedule()
        messageset_data = {
            'short_name': short_name,
            'notes': notes,
            'next_set': next_set,
            'default_schedule': schedule,
            'channel': channel,
        }
        return MessageSet.objects.create(**messageset_data)


class AuthenticatedAPITestCase(MessageSetTestMixin, APITestCase):

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
        self.assertEqual(response.data['hour'], '*')
        self.assertEqual(response.data['minute'], '0')
        d = Schedule.objects.last()
        self.assertEqual(d.cron_string, '0 * * * *')

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

    def test_list_schedule(self):
        # Setup
        schedules = []
        for i in range(3):
            schedules.append(self.make_schedule())
        # Execute
        response = self.client.get('/api/v1/schedule/',
                                   content_type='application/json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check first page
        body = response.json()
        self.assertEqual(len(body['results']), 2)
        self.assertEqual(body['results'][0]['id'], schedules[0].id)
        self.assertEqual(body['results'][1]['id'], schedules[1].id)
        self.assertIsNone(body['previous'])
        self.assertIsNotNone(body['next'])

        # Check next page
        body = self.client.get(body['next']).json()
        self.assertEqual(len(body['results']), 1)
        self.assertEqual(body['results'][0]['id'], schedules[2].id)
        self.assertIsNotNone(body['previous'])
        self.assertIsNone(body['next'])

        # Check previous page
        body = self.client.get(body['previous']).json()
        self.assertEqual(len(body['results']), 2)
        self.assertEqual(body['results'][0]['id'], schedules[0].id)
        self.assertEqual(body['results'][1]['id'], schedules[1].id)
        self.assertIsNone(body['previous'])
        self.assertIsNotNone(body['next'])

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
        for i in range(3):
            self.make_messageset(short_name='messageset_%s' % i)
        # Execute
        response = self.client.get('/api/v1/messageset/',
                                   content_type='application/json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check first page
        body = response.json()
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["results"][0]["short_name"], "messageset_0")
        self.assertEqual(body["results"][1]["short_name"], "messageset_1")
        self.assertIsNone(body['previous'])
        self.assertIsNotNone(body['next'])

        # Check next page
        body = self.client.get(body['next']).json()
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["results"][0]["short_name"], "messageset_2")
        self.assertIsNotNone(body['previous'])
        self.assertIsNone(body['next'])

        # Check previous page
        body = self.client.get(body['previous']).json()
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["results"][0]["short_name"], "messageset_0")
        self.assertEqual(body["results"][1]["short_name"], "messageset_1")
        self.assertIsNone(body['previous'])
        self.assertIsNotNone(body['next'])

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
        self.assertEqual(len(response.data["results"]), 1)
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

    def make_message(self, messageset, lang, seq=1):
        Message.objects.create(
            messageset=messageset, sequence_number=seq, lang=lang,
            text_content="Foo")

    def test_list_messages(self):
        messageset = self.make_messageset()
        # Setup
        for i in range(1, 4):
            self.make_message(messageset, "eng_ZA", i)
        # Execute
        response = self.client.get('/api/v1/message/',
                                   content_type='application/json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check first page
        body = response.json()
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["results"][0]["sequence_number"], 1)
        self.assertEqual(body["results"][1]["sequence_number"], 2)
        self.assertIsNone(body['previous'])
        self.assertIsNotNone(body['next'])

        # Check next page
        body = self.client.get(body['next']).json()
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["results"][0]["sequence_number"], 3)
        self.assertIsNotNone(body['previous'])
        self.assertIsNone(body['next'])

        # Check previous page
        body = self.client.get(body['previous']).json()
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["results"][0]["sequence_number"], 1)
        self.assertEqual(body["results"][1]["sequence_number"], 2)
        self.assertIsNone(body['previous'])
        self.assertIsNotNone(body['next'])

    def test_read_messageset_languages(self):
        """
        A GET Request should return all the messagesets with a unique list of
        languages available on each
        """
        # Setup
        messageset = self.make_messageset()
        self.make_message(messageset, 'eng')
        self.make_message(messageset, 'eng', seq=2)
        self.make_message(messageset, 'afr')
        messageset2 = self.make_messageset(short_name='messageset_two')
        self.make_message(messageset2, 'eng')
        self.make_message(messageset2, 'afr')
        self.make_message(messageset2, 'zul')
        self.make_message(messageset2, 'zul', seq=2)

        # Execute
        response = self.client.get('/api/v1/messageset_languages/',
                                   content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            json.loads(response.content.decode("utf-8")),
            {
                str(messageset.id): ["afr", "eng"],
                str(messageset2.id): ["afr", "eng", "zul"]
            }
        )


class TestMessageSet(MessageSetTestMixin, TestCase):
    def setUp(self):
        utils.disable_signals()

    def tearDown(self):
        utils.enable_signals()

    def test_get_all_run_dates(self):
        ms = self.make_messageset()
        for i in range(3):
            Message.objects.create(messageset=ms, sequence_number=i,
                                   lang='eng_ZA', text_content="Foo")

        start = datetime(2016, 11, 11, 7, 0, tzinfo=pytz.UTC)

        dates = ms.get_all_run_dates(start=start, lang='eng_ZA')

        self.assertEqual(dates, [
            datetime(2016, 11, 11, 8, 0, tzinfo=pytz.UTC),
            datetime(2016, 11, 11, 9, 0, tzinfo=pytz.UTC),
            datetime(2016, 11, 11, 10, 0, tzinfo=pytz.UTC)])

    def test_get_all_run_dates_none_for_lang(self):
        ms = self.make_messageset()
        for i in range(3):
            Message.objects.create(messageset=ms, sequence_number=i,
                                   lang='eng_ZA', text_content="Foo")

        start = datetime(2016, 11, 11, 7, 0, tzinfo=pytz.UTC)

        dates = ms.get_all_run_dates(start=start, lang='zul_ZA')

        self.assertEqual(dates, [])

    def test_get_all_run_dates_diff_schedule(self):
        ms = self.make_messageset()
        for i in range(3):
            Message.objects.create(messageset=ms, sequence_number=i,
                                   lang='eng_ZA', text_content="Foo")

        schedule = Schedule.objects.create(minute='0,30')

        start = datetime(2016, 11, 11, 7, 0, tzinfo=pytz.UTC)

        dates = ms.get_all_run_dates(start=start, lang='eng_ZA',
                                     schedule=schedule)

        self.assertEqual(dates, [
            datetime(2016, 11, 11, 7, 30, tzinfo=pytz.UTC),
            datetime(2016, 11, 11, 8, 0, tzinfo=pytz.UTC),
            datetime(2016, 11, 11, 8, 30, tzinfo=pytz.UTC)])

    def test_get_all_run_dates_diff_initial(self):
        ms = self.make_messageset()
        for i in range(3):
            Message.objects.create(messageset=ms, sequence_number=i,
                                   lang='eng_ZA', text_content="Foo")

        start = datetime(2016, 11, 11, 7, 0, tzinfo=pytz.UTC)

        dates = ms.get_all_run_dates(start=start, lang='eng_ZA',
                                     schedule=ms.default_schedule, initial=2)

        self.assertEqual(dates, [
            datetime(2016, 11, 11, 8, 0, tzinfo=pytz.UTC),
            datetime(2016, 11, 11, 9, 0, tzinfo=pytz.UTC)])


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


class TestAdmin(MessageSetTestMixin, TestCase):
    def setUp(self):
        utils.disable_signals()
        username = 'testuser'
        password = 'testpass'
        User.objects.create_superuser(
            username, 'testuser@example.com', password)
        self.client.login(username=username, password=password)
        self.change_url = reverse('admin:contentstore_messageset_changelist')

    def tearDown(self):
        utils.enable_signals()

    def test_clone_action_validation(self):
        message_set = self.make_messageset(short_name='messageset')
        response = self.client.post(self.change_url, {
            'action': 'clone_messageset',
            'do_action': 'yes',
            '_selected_action': message_set.pk,
            'short_name': message_set.short_name,
        })
        self.assertContains(
            response, 'A message set already exists with this name.')

    def test_clone_action(self):
        self.assertEqual(MessageSet.objects.count(), 0)
        message_set = self.make_messageset(short_name='messageset')
        self.assertEqual(MessageSet.objects.count(), 1)
        for i in range(10):
            message_set.messages.create(
                sequence_number=i, lang='eng_UK',
                text_content='message %s' % (i,))

        response = self.client.post(self.change_url, {
            'action': 'clone_messageset',
            'do_action': 'yes',
            '_selected_action': message_set.pk,
            'short_name': 'new short name!',
        })
        self.assertRedirects(response, self.change_url)
        self.assertEqual(MessageSet.objects.count(), 2)
        clone = MessageSet.objects.all().order_by('-pk').first()
        self.assertEqual(clone.short_name, 'new short name!')
        self.assertEqual(clone.messages.count(), message_set.messages.count())
        self.assertNotEqual(clone.pk, message_set.pk)


class TestSyncWelcomeAudio(AuthenticatedAPITestCase):

    def make_binarycontent(self, filename='hello.mp3'):
        data = {
            'content': filename,
        }
        return BinaryContent.objects.create(**data)

    @responses.activate
    @patch('contentstore.tasks.SyncAudioMessages._get_existing_files')
    @patch('sftpclone.sftpclone.SFTPClone.__init__')
    @patch('sftpclone.sftpclone.SFTPClone.run')
    def test_sync_welcome_audio(
            self, sftp_run_mock, sftp_mock, get_existing_mock):
        """
        When there is a POST to the sync audio api endpoint, it should sync
        only the missing audio files from the django api container then upload
        it to a sftp folder. The file should be cleaned up after.
        """

        sftp_run_mock.return_value = None
        sftp_mock.return_value = None
        get_existing_mock.return_value = ['other.mp3']

        self.make_binarycontent()

        responses.add(responses.GET,
                      "http://example.com/media/hello.mp3",
                      "test file content",
                      status=200, content_type='text/plain')

        response = self.client.post('/api/v1/sync_audio_files/',
                                    content_type='application/json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        sftp_mock.assert_called_with(
            '{}/{}/'.format(settings.BASE_DIR, settings.MEDIA_ROOT),
            'test:secret@localhost:test_directory', port=2222, delete=False)

        path = '{}/{}/hello.mp3'.format(settings.BASE_DIR, settings.MEDIA_ROOT)
        self.assertFalse(os.path.isfile(path))
