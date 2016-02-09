import json
import requests

from celery.task import Task
from celery.utils.log import get_task_logger
from celery.exceptions import SoftTimeLimitExceeded

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

logger = get_task_logger(__name__)

from .models import Subscription
from scheduler.client import SchedulerApiClient
from contentstore.models import Schedule, MessageSet, Message


class Schedule_Create(Task):

    """ Task to tell scheduler a new subscription created
    """
    name = "seed_staged_based_messaging.subscriptions.tasks.schedule_create"

    def scheduler_client(self):
        return SchedulerApiClient(
            username=settings.SCHEDULER_USERNAME,
            password=settings.SCHEDULER_PASSWORD,
            api_url=settings.SCHEDULER_URL)

    def schedule_to_cron(self, schedule):
        return "%s %s %s %s %s" % (
            schedule["minute"],
            schedule["hour"],
            schedule["day_of_month"],
            schedule["month_of_year"],
            schedule["day_of_week"]
        )

    def run(self, subscription_id, **kwargs):
        """ Returns scheduler-id
        """

        l = self.get_logger(**kwargs)
        l.info("Creating schedule for <%s>" % (subscription_id,))
        try:
            subscription = Subscription.objects.get(id=subscription_id)
            scheduler = self.scheduler_client()
            # get the subscription schedule/protocol from content store
            l.info("Loading contentstore schedule <%s>" % (
                subscription.schedule,))
            csschedule = Schedule.objects.get(pk=subscription.schedule)
            # get the messageset length for frequency
            messageset = MessageSet.objects.get(pk=subscription.messageset_id)
            subscription.metadata["frequency"] = \
                str(len(messageset["messages"]))
            # Build the schedule POST create object
            schedule = {
                "subscriptionId": subscription_id,
                "frequency": subscription.metadata["frequency"],
                "sendCounter": subscription.next_sequence_number,
                "cronDefinition": self.schedule_to_cron(csschedule),
                "endpoint": "%s/%s/send" % (
                    settings.SUBSCRIPTIONS_URL, subscription_id)
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


class Create_Message(Task):

    """ Task to create and populate a message with content
    """
    name = "seed_staged_based_messaging.subscriptions.tasks.create_message"

    def run(self, contact_id, messageset_id, sequence_number, lang,
            subscription_id, **kwargs):
        """ Returns success message
        """

        l = self.get_logger(**kwargs)
        l.info("Creating Outbound Message and Content")
        try:
            # should only return one object
            messages = Message.objects.filter(messageset=messageset_id,
                                              sequence_number=sequence_number,
                                              lang=lang)
            if len(messages) > 0:
                # if more than one matching message in Content store due to
                # poor management then we just use the first message
                message = Message[0]

                # Create the message which will trigger send task
                outbound_data = {
                    "contact_id": contact_id,
                    "content": message.text_content,
                    "metadata": {
                        "voice_speech_url": message.binary_content.content,
                        "subscription_id": subscription_id
                    }
                }
                result = requests.post(
                    "%s/outbound/" % settings.MESSAGESTORE_URL,
                    headers={'Content-Type': 'application/json',
                             'Authorisation': 'Token %s' % (
                                 settings.MESSAGESTORE_API_TOKEN)},
                    data=json.dumps(outbound_data),
                    verify=False
                )
                return "New message created <%s>" % result.data["id"]
            return "No message found for messageset <%s>, \
                    sequence_number <%s>, lang <%s>" % (
                messageset_id, sequence_number, lang, )

        except SoftTimeLimitExceeded:
            logger.error(
                'Soft time limit exceed processing message creation task \
                 via Celery.',
                exc_info=True)

create_message = Create_Message()
