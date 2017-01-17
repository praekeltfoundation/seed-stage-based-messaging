import requests
import json
try:
    from urlparse import urlunparse
except ImportError:
    from urllib.parse import urlunparse

from celery.task import Task
from celery.utils.log import get_task_logger
from celery.exceptions import SoftTimeLimitExceeded

from django.db.models import Count
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.sites.shortcuts import get_current_site
from django.utils.timezone import now
from go_http.metrics import MetricsApiClient

from .models import Subscription
from seed_stage_based_messaging import utils
from contentstore.models import Message, MessageSet, Schedule
from seed_services_client import SchedulerApiClient

logger = get_task_logger(__name__)


def get_metric_client(session=None):
    return MetricsApiClient(
        auth_token=settings.METRICS_AUTH_TOKEN,
        api_url=settings.METRICS_URL,
        session=session)


def make_absolute_url(path):
    # NOTE: We're using the default site as set by
    #       settings.SITE_ID and the Sites framework
    site = get_current_site(None)
    return urlunparse(
        ('https' if settings.USE_SSL else 'http',
         site.domain, path,
         '', '', ''))


class FireMetric(Task):

    """ Fires a metric using the MetricsApiClient
    """
    name = "subscriptions.tasks.fire_metric"

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
        except Subscription.DoesNotExist:
            logger.error('Could not load subscription <%s>' % subscription_id,
                         exc_info=True)
            return

        try:
            # start here
            if subscription.process_status == 0 and \
               subscription.completed is not True and \
               subscription.active is True:

                # Try load message first,
                l.info("Loading Message")
                message = Message.objects.get(
                    messageset=subscription.messageset,
                    sequence_number=subscription.next_sequence_number,
                    lang=subscription.lang)

                l.debug("setting process status to 1")
                subscription.process_status = 1  # in process
                l.debug("saving subscription")
                subscription.save()

                l.info("Loading Initial Recipient Identity")
                to_addr = None
                initial_id = utils.get_identity(subscription.identity)
                if "communicate_through" in initial_id and \
                        initial_id["communicate_through"] is not None:
                    # we should not send messages to this ID. Load listed ID.
                    to_addr = utils.get_identity_address(
                        initial_id["communicate_through"])
                else:
                    # set recipient data
                    to_addr = utils.get_identity_address(subscription.identity)
                l.debug("to_addr determined - %s" % to_addr)

                if to_addr is not None:
                    l.info("Preparing message payload with: %s" % message.id)  # noqa
                    payload = {
                        "to_addr": to_addr,
                        "delivered": "false",
                        "metadata": {}
                    }
                    if subscription.messageset.content_type == "text":
                        l.debug("Determining payload content")
                        if subscription.metadata is not None and \
                           "prepend_next_delivery" in subscription.metadata \
                           and subscription.metadata["prepend_next_delivery"] is not None:  # noqa
                            l.debug("Prepending next delivery")
                            payload["content"] = "%s\n%s" % (
                                subscription.metadata["prepend_next_delivery"],
                                message.text_content)
                            # clear prepend_next_delivery
                            l.debug("Clearing prepended message")
                            subscription.metadata[
                                "prepend_next_delivery"] = None
                            subscription.save()
                        else:
                            l.debug("Loading default content")
                            payload["content"] = message.text_content
                        l.debug("text content loaded")
                    else:
                        # TODO - audio media handling on MC
                        # audio

                        if subscription.metadata is not None and \
                           "prepend_next_delivery" in subscription.metadata \
                           and subscription.metadata["prepend_next_delivery"] is not None:  # noqa
                            payload["metadata"]["voice_speech_url"] = [
                                subscription.metadata["prepend_next_delivery"],
                                make_absolute_url(
                                    message.binary_content.content.url),
                            ]
                            # clear prepend_next_delivery
                            subscription.metadata[
                                "prepend_next_delivery"] = None
                            subscription.save()
                        else:
                            payload["metadata"]["voice_speech_url"] = \
                                make_absolute_url(
                                    message.binary_content.content.url)

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

                    l.debug("setting process status back to 0")
                    subscription.process_status = 0  # ready
                    l.debug("saving subscription")
                    subscription.save()

                    l.debug("firing post_send_process task")
                    post_send_process.apply_async(args=[subscription_id])
                    l.debug("fired post_send_process task")

                    l.debug("Firing SMS/OBD calls sent per message set metric")
                    send_type = utils.normalise_metric_name(
                                    subscription.messageset.content_type)
                    ms_name = utils.normalise_metric_name(
                                    subscription.messageset.short_name)
                    fire_metric.apply_async(kwargs={
                        "metric_name":
                            'message.{}.{}.sum'.format(send_type, ms_name),
                        "metric_value": 1.0
                    })
                    fire_metric.apply_async(kwargs={
                        "metric_name":
                            'message.{}.sum'.format(send_type),
                        "metric_value": 1.0
                    })

                    l.debug("Message queued for send. ID: <%s>" % str(result["id"]))  # noqa
                    return "Message queued for send. ID: <%s>" % str(result["id"])  # noqa
                else:
                    l.info("No valid recipient to_addr found")
                    subscription.process_status = -1  # Error
                    l.debug("saving subscription")
                    subscription.save()
                    l.debug("Firing error metric")
                    fire_metric.apply_async(kwargs={
                        "metric_name": 'subscriptions.send_next_message_errored.sum',  # noqa
                        "metric_value": 1.0
                    })
                    l.debug("Fired error metric")
                    return "Valid recipient could not be found"

            elif (subscription.process_status == 2 or
                  subscription.completed is True):
                # Disable the subscription's scheduler
                schedule_disable.apply_async(args=[subscription_id])
                l.info("Scheduler deactivation task fired")
                return "Schedule deactivation task fired"

            else:
                l.info("Message sending aborted - busy, broken or inactive")
                # TODO: retry if busy (process_status = 1)
                # TODO: be more specific about why it aborted
                return "Message sending aborted"

        except ObjectDoesNotExist:
            error = ('Missing Message: MessageSet: <%s>, Sequence Number: <%s>'
                     ', Lang: <%s>') % (
                subscription.messageset,
                subscription.next_sequence_number,
                subscription.lang)
            logger.error(error, exc_info=True)

        except SoftTimeLimitExceeded:
            logger.error(
                'Soft time limit exceed processing message send search '
                'via Celery.',
                exc_info=True)

        return False


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
            if subscription.process_status == 0:
                l.debug("setting process status to 1")
                subscription.process_status = 1  # in process
                l.debug("saving subscription")
                subscription.save()
                # Get set max
                set_max = subscription.messageset.messages.filter(
                    lang=subscription.lang).count()
                l.debug("set_max calculated - %s" % set_max)
                # Compare user position to max
                if subscription.next_sequence_number == set_max:
                    # Mark current as completed
                    l.debug("setting subscription completed")
                    subscription.completed = True
                    l.debug("setting subscription inactive")
                    subscription.active = False
                    l.debug("setting process status to 2")
                    subscription.process_status = 2  # Completed
                    l.debug("saving subscription")
                    subscription.save()
                    # If next set defined create new subscription
                    messageset = subscription.messageset
                    if messageset.next_set:
                        l.info("Creating new subscription for next set")
                        newsub = Subscription.objects.create(
                            identity=subscription.identity,
                            lang=subscription.lang,
                            messageset=messageset.next_set,
                            schedule=messageset.next_set.default_schedule
                        )
                        l.debug("Created Subscription <%s>" % newsub.id)
                else:
                    # More in this set so interate by one
                    l.debug("incrementing next_sequence_number")
                    subscription.next_sequence_number += 1
                    l.debug("setting process status back to 0")
                    subscription.process_status = 0
                    l.debug("saving subscription")
                    subscription.save()
                # return response
                return "Subscription for %s updated" % str(
                    subscription.id)
            else:
                l.info("post_send_process not executed")
                return "post_send_process not executed"

        except ObjectDoesNotExist:
            l.debug("subscription errored")
            subscription.process_status = -1  # Errored
            l.debug("saving subscription")
            subscription.save()
            logger.error('Unexpected error', exc_info=True)

        except SoftTimeLimitExceeded:
            logger.error(
                'Soft time limit exceed processing message send search '
                'via Celery.',
                exc_info=True)

        return False


post_send_process = PostSendProcess()


class ScheduleDisable(Task):

    """ Task to disable a subscription's schedule
    """
    name = "subscriptions.tasks.schedule_disable"

    def scheduler_client(self):
        return SchedulerApiClient(
            api_token=settings.SCHEDULER_API_TOKEN,
            api_url=settings.SCHEDULER_URL)

    def run(self, subscription_id, **kwargs):
        l = self.get_logger(**kwargs)
        l.info("Disabling schedule for <%s>" % (subscription_id,))
        try:
            subscription = Subscription.objects.get(id=subscription_id)
            try:
                schedule_id = subscription.metadata["scheduler_schedule_id"]
                scheduler = self.scheduler_client()
                scheduler.update_schedule(
                    subscription.metadata["scheduler_schedule_id"],
                    {"enabled": False}
                )
                l.info("Disabled schedule <%s> on scheduler for sub <%s>" % (
                    schedule_id, subscription_id))
                return True
            except:
                l.info("Schedule id not saved in subscription metadata")
                return False
        except ObjectDoesNotExist:
            logger.error('Missing Subscription', exc_info=True)
        except SoftTimeLimitExceeded:
            logger.error(
                'Soft time limit exceed processing schedule create '
                'via Celery.',
                exc_info=True)
        return False


schedule_disable = ScheduleDisable()


class ScheduleCreate(Task):

    """ Task to tell scheduler a new subscription created
    """
    name = "subscriptions.tasks.schedule_create"

    def scheduler_client(self):
        return SchedulerApiClient(
            api_token=settings.SCHEDULER_API_TOKEN,
            api_url=settings.SCHEDULER_URL)

    def run(self, subscription_id, **kwargs):
        """ Returns remote scheduler_id UUID
        """

        l = self.get_logger(**kwargs)
        l.info("Creating schedule for <%s>" % (subscription_id,))
        try:
            subscription = Subscription.objects.get(id=subscription_id)
            if subscription.process_status == 0:
                schedule = {
                    "frequency": None,
                    "cron_definition": subscription.schedule.cron_string,
                    "endpoint": "%s/%s/send" % (
                        settings.STAGE_BASED_MESSAGING_URL, subscription_id),
                    "auth_token": settings.SCHEDULER_INBOUND_API_TOKEN
                }
                scheduler = self.scheduler_client()
                result = scheduler.create_schedule(schedule)
                l.info("Created schedule <%s> on scheduler for sub <%s>" % (
                    result["id"], subscription_id))
                if subscription.metadata is None:
                    subscription.metadata = {"scheduler_schedule_id": result["id"]}  # noqa
                else:
                    subscription.metadata["scheduler_schedule_id"] = result["id"]  # noqa
                subscription.save()
                return result["id"]

        except ObjectDoesNotExist:
            logger.error('Missing Subscription', exc_info=True)

        except SoftTimeLimitExceeded:
            logger.error(
                'Soft time limit exceed processing schedule create '
                'via Celery.',
                exc_info=True)

        return False


schedule_create = ScheduleCreate()


class ScheduledMetrics(Task):

    """ Fires off tasks for all the metrics that should run
        on a schedule
    """
    name = "subscriptions.tasks.scheduled_metrics"

    def run(self, **kwargs):
        globs = globals()  # execute globals() outside for loop for efficiency
        for metric in settings.METRICS_SCHEDULED_TASKS:
            globs[metric].apply_async()

        return "%d Scheduled metrics launched" % len(
            settings.METRICS_SCHEDULED_TASKS)


scheduled_metrics = ScheduledMetrics()


class FireActiveLast(Task):

    """ Fires last active subscriptions count
    """
    name = "subscriptions.tasks.fire_active_last"

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
    name = "subscriptions.tasks.fire_created_last"

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
    name = "subscriptions.tasks.fire_broken_last"

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
    name = "subscriptions.tasks.fire_completed_last"  # noqa

    def run(self):
        completed_subs = Subscription.objects.filter(completed=True).count()
        return fire_metric.apply_async(kwargs={
            "metric_name": 'subscriptions.completed.last',
            "metric_value": completed_subs
        })


fire_completed_last = FireCompletedLast()


class FireIncompleteLast(Task):

    """ Fires last incomplete subscriptions count
    """
    name = "seed_stage_based_messaging.subscriptions.tasks.fire_incomplete_last"  # noqa

    def run(self):
        incomplete_subs = Subscription.objects.filter(completed=False).count()
        return fire_metric.apply_async(kwargs={
            "metric_name": 'subscriptions.incomplete.last',
            "metric_value": incomplete_subs
        })


fire_incomplete_last = FireIncompleteLast()


class FireMessageSetsTasks(Task):

    """ Fires off seperate tasks to count active subscriptions for each
        messageset found
    """
    name = "subscriptions.tasks.fire_messagesets_tasks"  # noqa

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

    name = "subscriptions.tasks.fire_messageset_last"  # noqa

    def run(self, msgset_id, short_name, **kwargs):
        active_msgset_subs = Subscription.objects.filter(
            messageset=msgset_id, active=True).count()
        return fire_metric.apply_async(kwargs={
            "metric_name": 'subscriptions.%s.active.last' % short_name,
            "metric_value": active_msgset_subs
        })


fire_messageset_last = FireMessageSetLast()


class FireWeekEstimateLast(Task):
    """Fires week estimated send counts.
    """
    name = "subscriptions.tasks.fire_week_estimate_last"

    def run(self):
        schedules = Schedule.objects.filter(
            subscriptions__active=True,
            subscriptions__completed=False,
            subscriptions__process_status=0
        ).annotate(total_subs=Count('subscriptions'))
        totals = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        for schedule in schedules:
            for day in range(7):
                if (str(day) in schedule.day_of_week or
                        '*' in schedule.day_of_week):
                    totals[day] = totals[day] + schedule.total_subs

        # Django's datetime's weekday method has Monday = 0
        # whereas the cron format used in the schedules has Sunday = 0
        sunday = totals.pop(0)
        totals[7] = sunday
        totals = {(k-1): v for k, v in totals.items()}

        today = now()
        for dow, total in totals.items():
            # Only fire the metric for today or days in the future so that
            # estimates for the week don't get updated after the day in
            # question.
            if dow >= (today.weekday()):
                fire_metric.apply_async(kwargs={
                    "metric_name": 'subscriptions.send.estimate.%s.last' % dow,
                    "metric_value": total
                })


fire_week_estimate_last = FireWeekEstimateLast()
