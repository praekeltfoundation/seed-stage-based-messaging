import requests
import json

from celery.task import Task
from celery.utils.log import get_task_logger
from celery.exceptions import SoftTimeLimitExceeded

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max
from go_http.metrics import MetricsApiClient

from .models import Subscription
from seed_stage_based_messaging import utils
from contentstore.models import Message, MessageSet
from scheduler.client import SchedulerApiClient

logger = get_task_logger(__name__)


def get_metric_client(session=None):
    return MetricsApiClient(
        auth_token=settings.METRICS_AUTH_TOKEN,
        api_url=settings.METRICS_URL,
        session=session)


class FireMetric(Task):

    """ Fires a metric using the MetricsApiClient
    """
    name = "seed_stage_based_messaging.subscriptions.tasks.fire_metric"

    def run(self, metric_name, metric_value, session=None, **kwargs):
        metric_value = float(metric_value)
        metric = {
            metric_name: metric_value
        }
        metric_client = get_metric_client(session=session)
        metric_client.fire(metric)
        return "Fired metric <%s> with value <%s>" % (
            metric_name, metric_value)

fire_metric = FireMetric()


class SendNextMessage(Task):

    """
    Task to load and contruct message and send them off
    """
    name = "subscriptions.tasks.send_next_message"

    class FailedEventRequest(Exception):

        """
        The attempted task failed because of a non-200 HTTP return
        code.
        """

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
            initial_id = utils.get_identity(subscription.identity)
            if "communicate_through" in initial_id and \
                    initial_id["communicate_through"] is not None:
                # we should not send messages to this ID. Load the listed one.
                to_addr = utils.get_identity_address(
                    initial_id["communicate_through"])
            else:
                # set recipient data
                to_addr = utils.get_identity_address(subscription.identity)
            if to_addr is not None:
                l.info("Preparing message payload with: %s" % message.id)
                payload = {
                    "to_addr": to_addr,
                    "delivered": "false",
                    "metadata": {}
                }
                if subscription.messageset.content_type == "text":
                    if "prepend_next_delivery" in subscription.metadata and \
                            subscription.metadata["prepend_next_delivery"] is not None:  # noqa
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
                            subscription.metadata["prepend_next_delivery"] is not None:  # noqa
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

send_next_message = SendNextMessage()


class PostSendProcess(Task):

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

post_send_process = PostSendProcess()


class ScheduleCreate(Task):

    """ Task to tell scheduler a new subscription created
    """
    name = "seed_stage_based_messaging.subscriptions.tasks.schedule_create"

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

schedule_create = ScheduleCreate()


class ScheduledMetrics(Task):

    """ Fires off tasks for all the metrics that should run
        on a schedule
    """
    name = "seed_stage_based_messaging.subscriptions.tasks.scheduled_metrics"

    def run(self, **kwargs):
        globs = globals()  # execute globals() outside for loop for efficiency
        for metric in settings.METRICS_SCHEDULED:
            globs[metric[1]].apply_async()  # metric[1] is the task name

        return "%d Scheduled metrics launched" % len(
            settings.METRICS_SCHEDULED)

scheduled_metrics = ScheduledMetrics()


class FireActiveLast(Task):

    """ Fires last active subscriptions count
    """
    name = "seed_stage_based_messaging.subscriptions.tasks.fire_active_last"

    def run(self):
        active_subs = Subscription.objects.filter(active=True).count()
        return fire_metric.apply_async(kwargs={
            "metric_name": 'subscriptions.active.last',
            "metric_value": active_subs
        })

fire_active_last = FireActiveLast()


class FireCreatedLast(Task):

    """ Fires last created subscriptions count
    """
    name = "seed_stage_based_messaging.subscriptions.tasks.fire_created_last"

    def run(self):
        created_subs = Subscription.objects.all().count()
        return fire_metric.apply_async(kwargs={
            "metric_name": 'subscriptions.created.last',
            "metric_value": created_subs
        })

fire_created_last = FireCreatedLast()


class FireBrokenLast(Task):

    """ Fires last broken subscriptions count
    """
    name = "seed_stage_based_messaging.subscriptions.tasks.fire_broken_last"

    def run(self):
        broken_subs = Subscription.objects.filter(process_status=-1).count()
        return fire_metric.apply_async(kwargs={
            "metric_name": 'subscriptions.broken.last',
            "metric_value": broken_subs
        })

fire_broken_last = FireBrokenLast()


class FireCompletedLast(Task):

    """ Fires last completed subscriptions count
    """
    name = "seed_stage_based_messaging.subscriptions.tasks.fire_completed_last"  # noqa

    def run(self):
        completed_subs = Subscription.objects.filter(completed=True).count()
        return fire_metric.apply_async(kwargs={
            "metric_name": 'subscriptions.completed.last',
            "metric_value": completed_subs
        })

fire_completed_last = FireCompletedLast()


class FireMessageSetsTasks(Task):

    """ Fires off seperate tasks to count active subscriptions for each
        messageset found
    """
    name = "seed_stage_based_messaging.subscriptions.tasks.fire_messagesets_tasks"  # noqa

    def run(self, **kwargs):
        # get message sets
        messagesets = MessageSet.objects.all()
        for messageset in messagesets:
            fire_messageset_last.apply_async(kwargs={
                "msgset_id": messageset.id,
                "short_name": messageset.short_name
            })
        return "%d MessageSet metrics launched" % messagesets.count()

fire_messagesets_tasks = FireMessageSetsTasks()


class FireMessageSetLast(Task):

    name = "seed_stage_based_messaging.subscriptions.tasks.fire_messageset_last"  # noqa

    def run(self, msgset_id, short_name, **kwargs):
        active_msgset_subs = Subscription.objects.filter(
            messageset=msgset_id, active=True).count()
        return fire_metric.apply_async(kwargs={
            "metric_name": 'subscriptions.%s.active.last' % short_name,
            "metric_value": active_msgset_subs
        })

fire_messageset_last = FireMessageSetLast()
