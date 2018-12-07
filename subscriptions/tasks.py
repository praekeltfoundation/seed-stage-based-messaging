try:
    from urlparse import urlunparse
except ImportError:
    from urllib.parse import urlunparse

from celery.task import Task
from celery.utils.log import get_task_logger
from celery.exceptions import SoftTimeLimitExceeded
from demands import HTTPServiceError
from django.db.models import Count, Q
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.sites.shortcuts import get_current_site
from django.utils.timezone import now
from seed_services_client.metrics import MetricsApiClient
from requests.exceptions import ConnectionError, HTTPError, Timeout

from .models import (Subscription, SubscriptionSendFailure, EstimatedSend,
                     ResendRequest, BehindSubscription)
from seed_stage_based_messaging import utils
from seed_stage_based_messaging.celery import app
from contentstore.models import Message, Schedule
from seed_services_client import MessageSenderApiClient, SchedulerApiClient

logger = get_task_logger(__name__)


def get_metric_client(session=None):
    return MetricsApiClient(
        url=settings.METRICS_URL,
        auth=settings.METRICS_AUTH,
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
        metric_client.fire_metrics(**metric)
        return "Fired metric <%s> with value <%s>" % (
            metric_name, metric_value)


fire_metric = FireMetric()


class StoreResendRequest(Task):

    """
    Task to save resend request and trigger send last message to the user.
    """
    name = "subscriptions.tasks.store_resend_request"

    def run(self, subscription_id, **kwargs):
        resend_request = ResendRequest.objects.create(
            subscription_id=subscription_id)

        send_current_message.delay(subscription_id, resend_request.id)

        return "Message queued for resend, subscriber: {}".format(
            subscription_id)


store_resend_request = StoreResendRequest()


class BaseSendMessage(Task):

    """
    Base Task for sending messages
    """

    class FailedEventRequest(Exception):

        """
        The attempted task failed because of a non-200 HTTP return
        code.
        """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # This function only gets called once all retries have failed, not with
        # each retry, this was tested in real life and is tested on a Celery
        # level but doesn't work with unit tests when CELERY_ALWAYS_EAGER is
        # True.
        # The function is called directly in the unit tests to make sure this
        # functionality works
        if isinstance(args[0], dict):
            subscription_id = args[0]["subscription_id"]
        else:
            subscription_id = args[0]

        SubscriptionSendFailure.objects.create(
            subscription_id=subscription_id,
            initiated_at=self.request.eta or now(),
            reason=str(exc),
            task_id=task_id
        )
        super(BaseSendMessage, self).on_failure(exc, task_id, args, kwargs,
                                                einfo)


@app.task
def pre_send_process(subscription_id, resend_id=None):
    context = {"subscription_id": subscription_id}

    if resend_id:
        context["resend_id"] = resend_id

    logger.info("Loading Subscription")
    subscription = Subscription.objects.select_related("messageset").get(
        id=context["subscription_id"])

    context["identity"] = subscription.identity

    if not subscription.is_ready_for_processing:
        if (subscription.process_status == 2 or
                subscription.completed is True):
            # Subscription is complete
            logger.info("Subscription has completed")
            context['error'] = "Subscription has completed"

        else:
            logger.info("Message sending aborted - busy, broken or inactive")
            # TODO: retry if busy (process_status = 1)
            # TODO: be more specific about why it aborted
            context['error'] = ("Message sending aborted, status <%s>" %
                                subscription.process_status)
        return context

    try:
        logger.info("Loading Message")
        next_sequence_number = subscription.next_sequence_number
        if next_sequence_number > 1 and resend_id:
            next_sequence_number -= 1

        message = Message.objects.get(
            messageset=subscription.messageset,
            sequence_number=next_sequence_number,
            lang=subscription.lang)

        context["message_id"] = message.id
        if subscription.messageset.content_type == "text":
            context["message_text_content"] = message.text_content

        if message.binary_content:
            context["message_binary_content_url"] = \
                message.binary_content.content.url
    except ObjectDoesNotExist:
        error = ('Missing Message: MessageSet: <%s>, Sequence Number: <%s>'
                 ', Lang: <%s>') % (
            subscription.messageset,
            subscription.next_sequence_number,
            subscription.lang)
        logger.error(error, exc_info=True)
        context['error'] = "Message sending aborted, missing message"
        return context

    # Start processing
    logger.debug("setting process status to 1")
    subscription.process_status = 1  # in process
    logger.debug("saving subscription")
    subscription.save()

    return context


@app.task(
    autoretry_for=(HTTPError, ConnectionError, Timeout, HTTPServiceError,
                   SoftTimeLimitExceeded),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=15,
    acks_late=True,
    soft_time_limit=10,
    time_limit=15,
    base=BaseSendMessage
)
def get_identity_address(context):
    if "error" in context:
        return context

    to_addr = utils.get_identity_address(
        context["identity"], use_communicate_through=True)

    if to_addr is None:
        logger.info("No valid recipient to_addr found")
        subscription = Subscription.objects.get(id=context["subscription_id"])
        subscription.process_status = -1  # Error
        logger.debug("saving subscription")
        subscription.save()

        context['error'] = "Valid recipient could not be found"
    else:
        context["to_addr"] = to_addr

    return context


@app.task(
    autoretry_for=(HTTPError, ConnectionError, Timeout, HTTPServiceError,
                   SoftTimeLimitExceeded),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=15,
    acks_late=True,
    soft_time_limit=10,
    time_limit=15,
    base=BaseSendMessage
)
def send_message(context):
    if "error" in context:
        return context

    subscription = Subscription.objects.select_related("messageset").get(
            id=context["subscription_id"])

    payload = {
        "to_addr": context["to_addr"],
        "to_identity": subscription.identity,
        "delivered": "false",
        "resend": "true" if "resend_id" in context else "false",
        "metadata": {}
    }

    if subscription.messageset.channel:
        payload["channel"] = subscription.messageset.channel

    prepend_next = None
    if subscription.messageset.content_type == "text":
        logger.debug("Determining payload content")
        if subscription.metadata is not None and \
            "prepend_next_delivery" in subscription.metadata \
            and subscription.metadata["prepend_next_delivery"] is not None:  # noqa
            prepend_next = subscription.metadata["prepend_next_delivery"]
            logger.debug("Prepending next delivery")
            payload["content"] = "%s\n%s" % (
                subscription.metadata["prepend_next_delivery"],
                context["message_text_content"])
        else:
            logger.debug("Loading default content")
            payload["content"] = context["message_text_content"]

        if "message_binary_content_url" in context:
            payload["metadata"]["image_url"] = make_absolute_url(
                context["message_binary_content_url"])

        logger.debug("text content loaded")
    else:
        # TODO - audio media handling on MC
        # audio

        if subscription.metadata is not None and \
            "prepend_next_delivery" in subscription.metadata \
            and subscription.metadata["prepend_next_delivery"] is not None:  # noqa
            prepend_next = subscription.metadata["prepend_next_delivery"]
            payload["metadata"]["voice_speech_url"] = [
                subscription.metadata["prepend_next_delivery"],
                make_absolute_url(
                    context["message_binary_content_url"]),
            ]
        else:
            payload["metadata"]["voice_speech_url"] = [
                make_absolute_url(
                    context["message_binary_content_url"])
            ]

    if subscription.messageset_id in settings.DRY_RUN_MESSAGESETS:
        logger.info('Skipping sending of message')
    else:
        logger.info("Sending message to Message Sender")
        message_sender_client = MessageSenderApiClient(
            settings.MESSAGE_SENDER_TOKEN,
            settings.MESSAGE_SENDER_URL,
            retries=5,
            timeout=settings.DEFAULT_REQUEST_TIMEOUT,
        )
        result = message_sender_client.create_outbound(payload)
        context["outbound_id"] = result['id']

    if prepend_next:
        logger.debug("Clearing prepended message")
        subscription.metadata["prepend_next_delivery"] = None
    logger.debug("setting process status back to 0")
    subscription.process_status = 0  # ready
    logger.debug("saving subscription")
    subscription.save()

    logger.debug("Message queued for send. ID: <%s>" % str(
        context.get("outbound_id")))
    return context


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

    def run(self, context, **kwargs):
        """
        Load subscription and process
        """
        if "error" in context:
            return context

        log = self.get_logger(**kwargs)

        log.info("Loading Subscription")
        # Process moving to next message, next set or finished
        try:
            subscription = Subscription.objects.select_related(
                "messageset").get(id=context["subscription_id"])
            if subscription.process_status == 0:
                log.debug("setting process status to 1")
                subscription.process_status = 1  # in process
                log.debug("saving subscription")
                subscription.save()
                # Get set max
                set_max = subscription.messageset.messages.filter(
                    lang=subscription.lang).count()
                log.debug("set_max calculated - %s" % set_max)
                # Compare user position to max
                if subscription.next_sequence_number == set_max:
                    # Mark current as completed
                    log.debug("setting subscription completed")
                    subscription.completed = True
                    log.debug("setting subscription inactive")
                    subscription.active = False
                    log.debug("setting process status to 2")
                    subscription.process_status = 2  # Completed
                    log.debug("saving subscription")
                    subscription.save()
                    # If next set defined create new subscription
                    messageset = subscription.messageset
                    if messageset.next_set:
                        log.info("Creating new subscription for next set")
                        newsub = Subscription.objects.create(
                            identity=subscription.identity,
                            lang=subscription.lang,
                            messageset=messageset.next_set,
                            schedule=messageset.next_set.default_schedule
                        )
                        log.debug("Created Subscription <%s>" % newsub.id)
                else:
                    # More in this set so interate by one
                    log.debug("incrementing next_sequence_number")
                    subscription.next_sequence_number += 1
                    log.debug("setting process status back to 0")
                    subscription.process_status = 0
                    log.debug("saving subscription")
                    subscription.save()
                # return response
                return "Subscription for %s updated" % str(
                    subscription.id)
            else:
                log.info("post_send_process not executed")
                return "post_send_process not executed"

        except SoftTimeLimitExceeded:
            logger.error(
                'Soft time limit exceed processing message send search '
                'via Celery.',
                exc_info=True)

        return False


post_send_process = PostSendProcess()


@app.task
def post_send_process_resend(context):
    resend_request = ResendRequest.objects.get(id=context["resend_id"])
    if "outbound_id" in context:
        resend_request.outbound = context["outbound_id"]
    resend_request.message_id = context["message_id"]
    resend_request.save()


send_next_message = (
    pre_send_process.s()
    | get_identity_address.s()
    | send_message.s()
    | post_send_process.s()
)

send_current_message = (
    pre_send_process.s()
    | get_identity_address.s()
    | send_message.s()
    | post_send_process_resend.s()
)


class ScheduleDisable(Task):

    """ Task to disable a subscription's schedule
    """
    name = "subscriptions.tasks.schedule_disable"

    def scheduler_client(self):
        return SchedulerApiClient(
            settings.SCHEDULER_API_TOKEN,
            settings.SCHEDULER_URL)

    def run(self, subscription_id, **kwargs):
        log = self.get_logger(**kwargs)
        log.info("Disabling schedule for <%s>" % (subscription_id,))
        try:
            subscription = Subscription.objects.get(id=subscription_id)
            try:
                schedule_id = subscription.metadata["scheduler_schedule_id"]
                scheduler = self.scheduler_client()
                scheduler.update_schedule(
                    subscription.metadata["scheduler_schedule_id"],
                    {"enabled": False}
                )
                log.info("Disabled schedule <%s> on scheduler for sub <%s>" % (
                    schedule_id, subscription_id))
                return True
            except Exception:
                log.info("Schedule id not saved in subscription metadata")
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


class FireDailySendEstimate(Task):
    """Fires daily estimated send counts.
    """
    name = "subscriptions.tasks.fire_daily_send_estimate"

    def run(self):
        # Django's datetime's weekday method has Monday = 0
        # whereas the cron format used in the schedules has Sunday = 0
        day = now().weekday() + 1

        schedules = Schedule.objects.filter(
            Q(day_of_week__contains=day) | Q(day_of_week__contains='*'),
            subscriptions__active=True,
            subscriptions__completed=False,
            subscriptions__process_status=0
        ).values('subscriptions__messageset').annotate(
            total_subs=Count('subscriptions'),
            total_unique=Count('subscriptions__identity', distinct=True))

        for schedule in schedules:
            EstimatedSend.objects.get_or_create(
                send_date=now().date(),
                messageset_id=schedule['subscriptions__messageset'],
                estimate_subscriptions=schedule['total_subs'],
                estimate_identities=schedule['total_unique']
            )


fire_daily_send_estimate = FireDailySendEstimate()


class RequeueFailedTasks(Task):

    """
    Task to requeue failed schedules.
    """
    name = "subscriptions.tasks.requeue_failed_tasks"

    def run(self, **kwargs):
        log = self.get_logger(**kwargs)
        failures = SubscriptionSendFailure.objects
        log.info("Attempting to requeue <%s> failed Subscription sends" %
                 failures.all().count())
        for failure in failures.iterator():
            subscription_id = str(failure.subscription_id)
            # Cleanup the failure before requeueing it.
            failure.delete()
            send_next_message.delay(subscription_id)


requeue_failed_tasks = RequeueFailedTasks()


@app.task
def calculate_subscription_lifecycle(subscription_id):
    """
    Calculates the expected lifecycle position the subscription in
    subscription_ids, and creates a BehindSubscription entry for them.

    Args:
        subscription_id (str): ID of subscription to calculate lifecycle for
    """
    subscription = Subscription.objects.select_related(
        "messageset", "schedule"
    ).get(
        id=subscription_id
    )
    number, completed = subscription.get_expected_next_sequence_number()
    if number <= subscription.next_sequence_number and completed is False:
        return

    current_messageset = subscription.messageset
    current_sequence_number = subscription.next_sequence_number
    end_subscription = Subscription.fast_forward_lifecycle(
        subscription, save=False)[-1]
    BehindSubscription.objects.create(
        subscription=subscription,
        messages_behind=number - current_sequence_number,
        current_messageset=current_messageset,
        current_sequence_number=current_sequence_number,
        expected_messageset=end_subscription.messageset,
        expected_sequence_number=end_subscription.next_sequence_number,
    )


@app.task
def find_behind_subscriptions():
    """
    Finds any subscriptions that are behind according to where they should be,
    and creates a BehindSubscription entry for them.
    """
    subscriptions = Subscription.objects.filter(
        active=True, completed=False, process_status=0,
    ).values_list(
        "id", flat=True
    )
    for subscription_id in subscriptions.iterator():
        calculate_subscription_lifecycle.delay(str(subscription_id))
