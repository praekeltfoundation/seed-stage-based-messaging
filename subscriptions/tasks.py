try:
    from urlparse import urlunparse
except ImportError:
    from urllib.parse import urlunparse

from celery.task import Task
from celery.utils.log import get_task_logger
from celery.exceptions import SoftTimeLimitExceeded

from django.db.models import Count, Q
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.sites.shortcuts import get_current_site
from django.utils.timezone import now
from seed_services_client.metrics import MetricsApiClient
from requests import exceptions as requests_exceptions

from .models import (Subscription, SubscriptionSendFailure, EstimatedSend,
                     ResendRequest)
from seed_stage_based_messaging import utils
from contentstore.models import Message, MessageSet, Schedule
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

        send_current_message(subscription_id, resend_id=resend_request.id)

        return "Message queued for resend, subscriber: {}".format(
            subscription_id)


store_resend_request = StoreResendRequest()


class BaseSendMessage(Task):

    """
    Task to load and contruct message and send them off
    """
    default_retry_delay = 5
    max_retries = 5

    class FailedEventRequest(Exception):

        """
        The attempted task failed because of a non-200 HTTP return
        code.
        """

    def get_message_to_send(self, subscription):
        message = Message.objects.get(
            messageset=subscription.messageset,
            sequence_number=subscription.next_sequence_number,
            lang=subscription.lang)

        return message

    def create_initial_payload(self, to_addr, subscription):
        payload = {
            "to_addr": to_addr,
            "to_identity": subscription.identity,
            "delivered": "false",
            "resend": "false",
            "metadata": {}
        }

        if subscription.messageset.channel:
            payload["channel"] = subscription.messageset.channel

        return payload

    def start_post_send_process(self, subscription_id, outbound_id):
        post_send_process(subscription_id)

    def send_message(
            self, log, payload, subscription, prepend_next, retry_delay):
        """
        Sends the specified message to the message sender, handling errors
        and retrying the task if necessary
        """
        log.info("Sending message to Message Sender")
        message_sender_client = MessageSenderApiClient(
            settings.MESSAGE_SENDER_TOKEN,
            settings.MESSAGE_SENDER_URL,
            retries=5,
            timeout=settings.DEFAULT_REQUEST_TIMEOUT,
        )
        try:
            return message_sender_client.create_outbound(payload)
        except requests_exceptions.ConnectionError as exc:
            log.info('Connection Error to Message Sender')
            fire_metric.delay('sbm.send_next_message.connection_error.sum', 1)
            # Reset the prepend next delivery that was cleared above.
            if prepend_next is not None:
                subscription.metadata["prepend_next_delivery"] = prepend_next
            subscription.process_status = 0
            subscription.save()
            self.retry(exc=exc, countdown=retry_delay)
        except requests_exceptions.HTTPError as exc:
            # Recoverable HTTP errors: 500, 401
            log.info('Message Sender Request failed due to status: %s' %
                     exc.response.status_code)
            metric_name = ('sbm.send_next_message.http_error.%s.sum' %
                           exc.response.status_code)
            fire_metric.delay(metric_name, 1)
            # Reset the prepend next delivery that was cleared above.
            if prepend_next is not None:
                subscription.metadata["prepend_next_delivery"] = prepend_next
            subscription.process_status = 0
            subscription.save()
            self.retry(exc=exc, countdown=retry_delay)
        except requests_exceptions.Timeout as exc:
            log.info('Message Sender Request failed due to timeout')
            fire_metric.delay('sbm.send_next_message.timeout.sum', 1)
            # Reset the prepend next delivery that was cleared above.
            if prepend_next is not None:
                subscription.metadata["prepend_next_delivery"] = prepend_next
            subscription.process_status = 0
            subscription.save()
            self.retry(exc=exc, countdown=retry_delay)

    def run(self, subscription_id, resend=None, **kwargs):
        """
        Load and contruct message and send them off
        """
        log = self.get_logger(**kwargs)

        log.info("Loading Subscription")
        try:
            subscription = Subscription.objects.get(id=subscription_id)
        except Subscription.DoesNotExist:
            logger.error('Could not load subscription <%s>' % subscription_id,
                         exc_info=True)
            return

        if not subscription.is_ready_for_processing:
            if (subscription.process_status == 2 or
                    subscription.completed is True):
                # Disable the subscription's scheduler
                schedule_disable.apply_async(args=[subscription_id])
                log.info("Scheduler deactivation task fired")
                return "Schedule deactivation task fired"

            else:
                log.info("Message sending aborted - busy, broken or inactive")
                # TODO: retry if busy (process_status = 1)
                # TODO: be more specific about why it aborted
                return ("Message sending aborted, status <%s>" %
                        subscription.process_status)

        try:
            log.info("Loading Message")
            message = self.get_message_to_send(subscription)
        except ObjectDoesNotExist:
            error = ('Missing Message: MessageSet: <%s>, Sequence Number: <%s>'
                     ', Lang: <%s>') % (
                subscription.messageset,
                subscription.next_sequence_number,
                subscription.lang)
            logger.error(error, exc_info=True)
            return "Message sending aborted, missing message"

        if self.request.retries > 0:
            retry_delay = utils.calculate_retry_delay(self.request.retries)
        else:
            retry_delay = self.default_retry_delay

        # Start processing
        log.debug("setting process status to 1")
        subscription.process_status = 1  # in process
        log.debug("saving subscription")
        subscription.save()

        log.info("Loading Initial Recipient Identity")
        try:
            to_addr = utils.get_identity_address(
                subscription.identity,
                use_communicate_through=True)
        except requests_exceptions.ConnectionError as exc:
            log.info('Connection Error to Identity Store')
            fire_metric.delay('sbm.send_next_message.connection_error.sum', 1)
            subscription.process_status = 0
            subscription.save()
            self.retry(exc=exc, countdown=retry_delay)
        except requests_exceptions.HTTPError as exc:
            # Recoverable HTTP errors: 500, 401
            log.info('Identity Store Request failed due to status: %s' %
                     exc.response.status_code)
            metric_name = ('sbm.send_next_message.http_error.%s.sum' %
                           exc.response.status_code)
            fire_metric.delay(metric_name, 1)
            subscription.process_status = 0
            subscription.save()
            self.retry(exc=exc, countdown=retry_delay)
        except requests_exceptions.Timeout as exc:
            log.info('Identity Store Request failed due to timeout')
            fire_metric.delay('sbm.send_next_message.timeout.sum', 1)
            subscription.process_status = 0
            subscription.save()
            self.retry(exc=exc, countdown=retry_delay)
        log.debug("to_addr determined - %s" % to_addr)

        if to_addr is None:
            log.info("No valid recipient to_addr found")
            subscription.process_status = -1  # Error
            log.debug("saving subscription")
            subscription.save()
            log.debug("Firing error metric")
            fire_metric.apply_async(kwargs={
                "metric_name": 'subscriptions.send_next_message_errored.sum',  # noqa
                "metric_value": 1.0
            })
            log.debug("Fired error metric")
            return "Valid recipient could not be found"

        # All preconditions have been met
        log.info("Preparing message payload with: %s" % message.id)  # noqa

        payload = self.create_initial_payload(to_addr, subscription)

        prepend_next = None
        if subscription.messageset.content_type == "text":
            log.debug("Determining payload content")
            if subscription.metadata is not None and \
               "prepend_next_delivery" in subscription.metadata \
               and subscription.metadata["prepend_next_delivery"] is not None:  # noqa
                prepend_next = subscription.metadata["prepend_next_delivery"]
                log.debug("Prepending next delivery")
                payload["content"] = "%s\n%s" % (
                    subscription.metadata["prepend_next_delivery"],
                    message.text_content)
                # clear prepend_next_delivery
                log.debug("Clearing prepended message")
                subscription.metadata[
                    "prepend_next_delivery"] = None
                subscription.save()
            else:
                log.debug("Loading default content")
                payload["content"] = message.text_content
            log.debug("text content loaded")
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
                        message.binary_content.content.url),
                ]
                # clear prepend_next_delivery
                subscription.metadata[
                    "prepend_next_delivery"] = None
                subscription.save()
            else:
                payload["metadata"]["voice_speech_url"] = [
                    make_absolute_url(
                        message.binary_content.content.url)
                ]

        if subscription.messageset_id in settings.DRY_RUN_MESSAGESETS:
            log.info('Skipping sending of message')
            message_id = None
        else:
            result = self.send_message(
                log, payload, subscription, prepend_next, retry_delay)
            message_id = result['id']

        log.debug("setting process status back to 0")
        subscription.process_status = 0  # ready
        log.debug("saving subscription")
        subscription.save()

        log.debug("starting post_send_process task")
        self.start_post_send_process(subscription_id, message_id)
        log.debug("finished post_send_process task")

        log.debug("Firing SMS/OBD calls sent per message set metric")
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

        log.debug("Message queued for send. ID: <%s>" % str(message_id))
        return "Message queued for send. ID: <%s>" % str(message_id)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if self.request.retries == self.max_retries:
            SubscriptionSendFailure.objects.create(
                subscription_id=args[0],
                initiated_at=self.request.eta,
                reason=einfo.exception.message,
                task_id=task_id
            )
        super(BaseSendMessage, self).on_failure(exc, task_id, args,
                                                kwargs, einfo)


class SendNextMessage(BaseSendMessage):

    """
    Task to load and contruct message and send them off
    """
    name = "subscriptions.tasks.send_next_message"


send_next_message = SendNextMessage()


class SendCurrentMessage(BaseSendMessage):

    """
    Task to load and contruct last sent message and send it again
    """
    name = "subscriptions.tasks.send_current_message"

    def run(self, subscription_id, resend_id, **kwargs):
        self.resend_id = resend_id
        return super(SendCurrentMessage, self).run(subscription_id, **kwargs)

    def create_initial_payload(self, to_addr, subscription):
        payload = super(SendCurrentMessage, self).create_initial_payload(
            to_addr, subscription)

        payload['resend'] = "true"

        return payload

    def get_message_to_send(self, subscription):
        next_sequence_number = subscription.next_sequence_number
        if next_sequence_number > 1:
            next_sequence_number -= 1

        message = Message.objects.get(
            messageset=subscription.messageset,
            sequence_number=next_sequence_number,
            lang=subscription.lang)

        self.message = message

        return message

    def start_post_send_process(self, subscription_id, outbound_id):
        resend_request = ResendRequest.objects.get(id=self.resend_id)
        resend_request.outbound = outbound_id
        resend_request.message = self.message
        resend_request.save()


send_current_message = SendCurrentMessage()


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
        log = self.get_logger(**kwargs)

        log.info("Loading Subscription")
        # Process moving to next message, next set or finished
        try:
            subscription = Subscription.objects.get(id=subscription_id)
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


class ScheduleCreate(Task):

    """ Task to tell scheduler a new subscription created
    """
    name = "subscriptions.tasks.schedule_create"

    def scheduler_client(self):
        return SchedulerApiClient(
            settings.SCHEDULER_API_TOKEN,
            settings.SCHEDULER_URL)

    def run(self, subscription_id, **kwargs):
        """ Returns remote scheduler_id UUID
        """

        log = self.get_logger(**kwargs)
        log.info("Creating schedule for <%s>" % (subscription_id,))
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
                log.info("Created schedule <%s> on scheduler for sub <%s>" % (
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
