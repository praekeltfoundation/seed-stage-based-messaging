import requests
import json

from celery.task import Task
from celery.utils.log import get_task_logger
from celery.exceptions import SoftTimeLimitExceeded

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max

from .models import Subscription
from contentstore.models import Message
from scheduler.client import SchedulerApiClient

logger = get_task_logger(__name__)


class Send_Next_Message(Task):

    """
    Task to load and contruct message and send them off
    """
    name = "subscriptions.tasks.send_next_message"

    class FailedEventRequest(Exception):

        """
        The attempted task failed because of a non-200 HTTP return
        code.
        """

    def get_identity(self, identity_uuid):
        url = "%s/%s/%s/" % (settings.IDENTITY_STORE_URL,
                             "identities", identity_uuid)
        headers = {'Authorization': ['Token %s' % (
            settings.IDENTITY_STORE_TOKEN, )],
            'Content-Type': ['application/json']}
        r = requests.get(url, headers=headers)
        return r.json()

    def get_identity_address(self, identity_uuid):
        url = "%s/%s/%s/addresses/msisdn" % (settings.IDENTITY_STORE_URL,
                                             "identities", identity_uuid)
        params = {"default": True}
        headers = {'Authorization': ['Token %s' % (
            settings.IDENTITY_STORE_TOKEN, )],
            'Content-Type': ['application/json']}
        r = requests.get(url, params=params, headers=headers).json()
        if len(r["results"]) > 0:
            return r["results"][0]
        else:
            return None

    def run(self, subscription_id, **kwargs):
        """
        Load and contruct message and send them off
        """
        l = self.get_logger(**kwargs)

        l.info("Loading Subscription")
        try:
            subscription = Subscription.objects.get(id=subscription_id)
            # start here
            l.info("Loading Message")
            message = Message.objects.get(
                messageset=subscription.messageset,
                sequence_number=subscription.next_sequence_number,
                lang=subscription.lang)
            l.info("Loading Initial Recipient Identity")
            initial_id = self.get_identity(subscription.identity)
            if "communicate_through" in initial_id and \
                    initial_id["communicate_through"] is not None:
                # we should not send messages to this ID. Load the listed one.
                to_addr = self.get_identity_address(
                    initial_id["communicate_through"])
            else:
                # set recipient data
                to_addr = self.get_identity_address(subscription.identity)
            if to_addr is not None:
                l.info("Preparing message payload with: %s" % message.id)
                payload = {
                    "to_addr": to_addr,
                    "delivered": "false",
                    "metadata": {}
                }
                if subscription.messageset.content_type == "text":
                    if "prepend_next_delivery" in subscription.metadata and \
                            subscription.metadata is not None:
                        payload["content"] = "%s\n%s" % (
                            subscription.metadata["prepend_next_delivery"],
                            message.text_content)
                        # clear prepend_next_delivery
                        subscription.metadata["prepend_next_delivery"] = None
                        subscription.save()
                    else:
                        payload["content"] = message.text_content
                else:
                    # TODO - audio media handling on MC
                    # audio
                    if "prepend_next_delivery" in subscription.metadata and \
                            subscription.metadata is not None:
                        payload["metadata"]["voice_speech_url"] = [
                            subscription.metadata["prepend_next_delivery"],
                            message.binary_content.content.url
                        ]
                        # clear prepend_next_delivery
                        subscription.metadata["prepend_next_delivery"] = None
                        subscription.save()
                    else:
                        payload["metadata"]["voice_speech_url"] = \
                            message.binary_content.content.url
                l.info("Sending message to Message Sender")
                result = requests.post(
                    url="%s/outbound/" % settings.MESSAGE_SENDER_URL,
                    data=json.dumps(payload),
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': 'Token %s' % (
                            settings.MESSAGE_SENDER_TOKEN,)
                    }
                ).json()
                post_send_process.apply_async(args=[subscription_id])
                l.info("Message queued for send. ID: <%s>" % str(result["id"]))
            else:
                l.info("No valid recipient to_addr found")
                subscription.process_status = -1  # Error
                subscription.save()
        except ObjectDoesNotExist:
            logger.error('Missing Message', exc_info=True)

        except SoftTimeLimitExceeded:
            logger.error(
                'Soft time limit exceed processing message send search \
                 via Celery.',
                exc_info=True)

send_next_message = Send_Next_Message()


class Post_Send_Process(Task):

    """
    Task to ensure subscription is bumped or converted
    """
    name = "subscriptions.tasks.post_send_process"

    class FailedEventRequest(Exception):

        """
        The attempted task failed because of a non-200 HTTP return
        code.
        """

    def run(self, subscription_id, **kwargs):
        """
        Load subscription and process
        """
        l = self.get_logger(**kwargs)

        l.info("Loading Subscription")
        # Process moving to next message, next set or finished
        try:
            subscription = Subscription.objects.get(id=subscription_id)
            # Get set max
            set_max = Message.objects.filter(
                messageset=subscription.messageset
            ).aggregate(Max('sequence_number'))["sequence_number__max"]
            # Compare user position to max
            if subscription.next_sequence_number == set_max:
                # Mark current as completed
                subscription.completed = True
                subscription.active = False
                subscription.process_status = 2  # Completed
                subscription.save()
                # If next set defined create new subscription
                messageset = subscription.messageset
                if messageset.next_set:
                    # clone existing minus PK as recommended in
                    # https://docs.djangoproject.com/en/1.9/topics/db/queries/
                    # copying-model-instances
                    subscription.pk = None
                    subscription.process_status = 0  # Ready
                    subscription.active = True
                    subscription.completed = False
                    subscription.next_sequence_number = 1
                    subscription = subscription
                    subscription.message_set = messageset.next_set
                    subscription.schedule = (
                        subscription.messageset.default_schedule)
                    subscription.save()
            else:
                # More in this set so interate by one
                subscription.next_sequence_number += 1
                subscription.save()
            # return response
            return "Subscription for %s updated" % str(subscription.id)
        except ObjectDoesNotExist:
            subscription.process_status = -1  # Errored
            subscription.save()
            logger.error('Unexpected error', exc_info=True)

        except SoftTimeLimitExceeded:
            logger.error(
                'Soft time limit exceed processing message send search \
                 via Celery.',
                exc_info=True)

post_send_process = Post_Send_Process()


class Schedule_Create(Task):

    """ Task to tell scheduler a new subscription created
    """
    name = "seed_staged_based_messaging.subscriptions.tasks.schedule_create"

    def scheduler_client(self):
        return SchedulerApiClient(
            api_token=settings.SCHEDULER_API_TOKEN,
            api_url=settings.SCHEDULER_URL)

    def schedule_to_cron(self, schedule):
        return "%s %s %s %s %s" % (
            schedule.minute,
            schedule.hour,
            schedule.day_of_month,
            schedule.month_of_year,
            schedule.day_of_week
        )

    def run(self, subscription_id, **kwargs):
        """ Returns remote scheduler_id UUID
        """

        l = self.get_logger(**kwargs)
        l.info("Creating schedule for <%s>" % (subscription_id,))
        try:
            subscription = Subscription.objects.get(id=subscription_id)
            scheduler = self.scheduler_client()
            # get the messageset length for frequency calc
            message_count = subscription.messageset.messages.all().count()
            # next_sequence_number is for setting non-one start position
            frequency = (message_count - subscription.next_sequence_number) + 1
            # Build the schedule POST create object
            schedule = {
                "frequency": frequency,
                "cron_definition":
                    self.schedule_to_cron(subscription.schedule),
                "endpoint": "%s/%s/send" % (
                    settings.STAGE_BASED_MESSAGING_URL, subscription_id),
                "auth_token": settings.SCHEDULER_INBOUND_API_TOKEN
            }
            result = scheduler.create_schedule(schedule)
            l.info("Created schedule <%s> on scheduler for sub <%s>" % (
                result["id"], subscription_id))
            subscription.metadata["scheduler_schedule_id"] = result["id"]
            subscription.save()
            return result["id"]

        except ObjectDoesNotExist:
            logger.error('Missing Subscription', exc_info=True)

        except SoftTimeLimitExceeded:
            logger.error(
                'Soft time limit exceed processing schedule create \
                 via Celery.',
                exc_info=True)

schedule_create = Schedule_Create()
