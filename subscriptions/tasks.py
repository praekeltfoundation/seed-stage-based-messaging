import json
import requests

from celery.task import Task
from celery.utils.log import get_task_logger
from celery.exceptions import SoftTimeLimitExceeded

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

logger = get_task_logger(__name__)

from .models import Subscription
from contentstore.models import Schedule, MessageSet, Message


class Schedule_Create(Task):

    """ Task to tell scheduler a new subscription created
    """
    name = "seed_staged_based_messaging.subscriptions.tasks.schedule_create"

    class FailedEventRequest(Exception):  # TODO

        """ The attempted task failed because of a non-200 HTTP return code.
        """

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
            # get the subscription schedule/protocol from content store
            l.info("Loading contentstore schedule <%s>" % (
                subscription.schedule,))
            cs_schedule = Schedule.objects.get(pk=subscription.schedule)
            # get the messageset length for frequency
            messageset = MessageSet.objects.get(pk=subscription.messageset_id)
            subscription.metadata["frequency"] = \
                str(len(messageset["messages"]))
            # Build the schedule POST create object
            schedule_data = {
                "subscriptionId": subscription_id,
                "frequency": subscription.metadata["frequency"],
                "sendCounter": subscription.next_sequence_number,
                "cronDefinition": self.schedule_to_cron(cs_schedule),
                "endpoint": "%s/subscriptions/%s/send" % (  # TODO ?
                    settings.CONTROL_URL, subscription_id)
            }
            result = requests.post(
                "%s/scheduler/" % settings.SCHEDULER_URL,  # TODO url
                headers={'Content-Type': 'application/json'},
                data=json.dumps(schedule_data),
                auth=(settings.SCHEDULER_USERNAME,
                      settings.SCHEDULER_PASSWORD),  # TODO Different Auth?
                verify=False
            )
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

    class FailedEventRequest(Exception):

        """ The attempted task failed because of a non-200 HTTP return code.
        """

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
                        "voice_speech_url": message.binary_content.content,  # TODO
                        "subscription_id": subscription_id
                    }
                }
                result = requests.post(
                    "%s/outbound/" % settings.MESSAGESTORE_URL,  # TODO url
                    headers={'Content-Type': 'application/json'},
                    data=json.dumps(outbound_data),
                    auth=(settings.MESSAGESTORE_USERNAME,
                          settings.MESSAGESTORE_PASSWORD),  # TODO Different Auth?
                    verify=False
                )
                return "New message created <%s>" % result["id"]  # TODO
            return "No message found for messageset <%s>, \
                    sequence_number <%s>, lang <%s>" % (
                messageset_id, sequence_number, lang, )

        except SoftTimeLimitExceeded:
            logger.error(
                'Soft time limit exceed processing message creation task \
                 via Celery.',
                exc_info=True)

create_message = Create_Message()
