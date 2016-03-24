import responses
import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.db.models.signals import post_save

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from .models import Subscription, fire_sub_action_if_new
from contentstore.models import Schedule, MessageSet, BinaryContent, Message
from .tasks import schedule_create


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

    def make_messageset(self):
        messageset_data = {
            'short_name': 'messageset_one',
            'notes': None,
            'next_set': None,
            'default_schedule': self.schedule
        }
        return MessageSet.objects.create(**messageset_data)

    def make_subscription(self):
        post_data = {
            "identity": "8646b7bc-b511-4965-a90b-e1145e398703",
            "messageset": self.messageset,
            "next_sequence_number": 1,
            "lang": "en_ZA",
            "active": True,
            "completed": False,
            "schedule": self.schedule,
            "process_status": 0,
            "metadata": {
                "source": "RapidProVoice"
            }
        }
        return Subscription.objects.create(**post_data)

    def _replace_post_save_hooks(self):
        def has_listeners():
            return post_save.has_listeners(Subscription)
        assert has_listeners(), (
            "Subscription model has no post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")
        post_save.disconnect(fire_sub_action_if_new, sender=Subscription)
        assert not has_listeners(), (
            "Subscription model still has post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")

    def _restore_post_save_hooks(self):
        def has_listeners():
            return post_save.has_listeners(Subscription)
        assert not has_listeners(), (
            "Subscription model still has post_save listeners. Make sure"
            " helpers removed them properly in earlier tests.")
        post_save.connect(fire_sub_action_if_new, sender=Subscription)

    def setUp(self):
        super(AuthenticatedAPITestCase, self).setUp()
        self._replace_post_save_hooks()

        self.username = 'testuser'
        self.password = 'testpass'
        self.user = User.objects.create_user(self.username,
                                             'testuser@example.com',
                                             self.password)
        token = Token.objects.create(user=self.user)
        self.token = token.key
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        self.schedule = self.make_schedule()
        self.messageset = self.make_messageset()

    def tearDown(self):
        self._restore_post_save_hooks()


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

    def test_create_subscription_data(self):
        # Setup
        post_subscription = {
            "identity": "7646b7bc-b511-4965-a90b-e1145e398703",
            "messageset": self.messageset.id,
            "next_sequence_number": 1,
            "lang": "en_ZA",
            "active": True,
            "completed": False,
            "schedule": self.schedule.id,
            "process_status": 0,
            "metadata": {
                "source": "RapidProVoice"
            }
        }
        # Execute
        response = self.client.post('/api/v1/subscriptions/',
                                    json.dumps(post_subscription),
                                    content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        d = Subscription.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(d.version, 1)
        self.assertEqual(d.messageset.id, self.messageset.id)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "en_ZA")
        self.assertEqual(d.active, True)
        self.assertEqual(d.completed, False)
        self.assertEqual(d.schedule.id, self.schedule.id)
        self.assertEqual(d.process_status, 0)
        self.assertEqual(d.metadata["source"], "RapidProVoice")

    def test_read_subscription_data(self):
        # Setup
        existing = self.make_subscription()
        # Execute
        response = self.client.get('/api/v1/subscriptions/%s/' % existing.id,
                                   content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        d = Subscription.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(d.version, 1)
        self.assertEqual(d.messageset.id, self.messageset.id)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "en_ZA")
        self.assertEqual(d.active, True)
        self.assertEqual(d.completed, False)
        self.assertEqual(d.schedule.id, self.schedule.id)
        self.assertEqual(d.process_status, 0)
        self.assertEqual(d.metadata["source"], "RapidProVoice")

    def test_update_subscription_data(self):
        # Setup
        existing = self.make_subscription()
        patch_subscription = {
            "next_sequence_number": 10,
            "active": False,
            "completed": True
        }
        # Execute
        response = self.client.patch('/api/v1/subscriptions/%s/' % existing.id,
                                     json.dumps(patch_subscription),
                                     content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        d = Subscription.objects.get(pk=existing.id)
        self.assertEqual(d.active, False)
        self.assertEqual(d.completed, True)
        self.assertEqual(d.next_sequence_number, 10)
        self.assertEqual(d.lang, "en_ZA")

    def test_delete_subscription_data(self):
        # Setup
        existing = self.make_subscription()
        # Execute
        response = self.client.delete(
            '/api/v1/subscriptions/%s/' % existing.id,
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        d = Subscription.objects.filter(id=existing.id).count()
        self.assertEqual(d, 0)


class TestCreateScheduleTask(AuthenticatedAPITestCase):

    @responses.activate
    def test_create_schedule_task(self):
        # Setup
        # make schedule
        schedule_data = {
            "minute": "1",
            "hour": "6",
            "day_of_week": "1",
            "day_of_month": "*",
            "month_of_year": "*"
        }
        schedule = Schedule.objects.create(**schedule_data)

        # make messageset
        messageset_data = {
            "short_name": "pregnancy",
            "notes": "Base pregancy set",
            "next_set": None,
            "default_schedule": schedule
        }
        messageset = MessageSet.objects.create(**messageset_data)

        # make binarycontent
        binarycontent_data1 = {
            "content": "fakefilename",
        }
        binarycontent1 = BinaryContent.objects.create(**binarycontent_data1)
        binarycontent_data2 = {
            "content": "fakefilename",
        }
        binarycontent2 = BinaryContent.objects.create(**binarycontent_data2)

        # make messages
        message_data1 = {
            "messageset": messageset,
            "sequence_number": 1,
            "lang": "en_ZA",
            "binary_content": binarycontent1,
        }
        Message.objects.create(**message_data1)
        message_data2 = {
            "messageset": messageset,
            "sequence_number": 2,
            "lang": "en_ZA",
            "binary_content": binarycontent2,
        }
        Message.objects.create(**message_data2)

        # make subscription
        post_data = {
            "identity": "8646b7bc-b511-4965-a90b-e1145e398703",
            "messageset": messageset,
            "next_sequence_number": 1,
            "lang": "en_ZA",
            "active": True,
            "completed": False,
            "schedule": schedule,
            "process_status": 0,
            "metadata": {
                "source": "RapidProVoice"
            }
        }
        existing = Subscription.objects.create(**post_data)

        # Create schedule
        schedule_post = {
            "class": "seedproject.scheduler.Schedule",
            "id": "11",
            "cronDefinition": "1 6 1 * *",
            "dateCreated": "2015-04-05T21:59:28Z",
            "endpoint": "%s/%s/%s/send" % (
                "http://seed-project/api/v1",
                "subscriptions",
                str(existing.id)),
            "frequency": 10,
            "messages": None,
            "nextSend": "2015-04-05T22:00:00Z",
            "sendCounter": 0,
            "subscriptionId": str(existing.id)
        }
        responses.add(responses.POST,
                      "http://seed-project/api/v1/scheduler/schedules",
                      json.dumps(schedule_post),
                      status=200, content_type='application/json')

        result = schedule_create.apply_async(args=[str(existing.id)])
        self.assertEqual(int(result.get()), 11)

        d = Subscription.objects.get(pk=existing.id)
        self.assertIsNotNone(d.id)
        self.assertEqual(d.metadata["scheduler_schedule_id"], "11")


class TestSubscriptionsWebhookListener(AuthenticatedAPITestCase):

    def test_webhook_subscription_data_good(self):
        # Setup
        post_webhook = {
            "hook": {
                "id": 5,
                "event": "subscriptionrequest.added",
                "target": "http://example.com/api/v1/subscriptions/request"
            },
            "data": {
                "messageset": self.messageset.id,
                "updated_at": "2016-02-17T07:59:42.831568+00:00",
                "identity": "7646b7bc-b511-4965-a90b-e1145e398703",
                "lang": "en_ZA",
                "created_at": "2016-02-17T07:59:42.831533+00:00",
                "id": "5282ed58-348f-4a54-b1ff-f702e36ec3cc",
                "next_sequence_number": 1,
                "schedule": self.schedule.id
            }
        }
        # Execute
        response = self.client.post('/api/v1/subscriptions/request',
                                    json.dumps(post_webhook),
                                    content_type='application/json')
        # Check
        print(response.json())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        d = Subscription.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(d.version, 1)
        self.assertEqual(d.messageset.id, self.messageset.id)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "en_ZA")
        self.assertEqual(d.active, True)
        self.assertEqual(d.completed, False)
        self.assertEqual(d.schedule.id, self.schedule.id)
        self.assertEqual(d.process_status, 0)

    def test_webhook_subscription_data_bad(self):
        # Setup with missing identity
        post_webhook = {
            "hook": {
                "id": 5,
                "event": "subscriptionrequest.added",
                "target": "http://example.com/api/v1/subscriptions/request"
            },
            "data": {
                "messageset": self.messageset.id,
                "updated_at": "2016-02-17T07:59:42.831568+00:00",
                "lang": "en_ZA",
                "created_at": "2016-02-17T07:59:42.831533+00:00",
                "id": "5282ed58-348f-4a54-b1ff-f702e36ec3cc",
                "next_sequence_number": 1,
                "schedule": self.schedule.id
            }
        }
        # Execute
        response = self.client.post('/api/v1/subscriptions/request',
                                    json.dumps(post_webhook),
                                    content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(),
                         {"identity": ["This field is required."]})
