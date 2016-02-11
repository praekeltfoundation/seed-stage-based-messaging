from celery.task import Task
from celery.utils.log import get_task_logger
from celery.exceptions import SoftTimeLimitExceeded

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from .models import Subscription
from scheduler.client import SchedulerApiClient
from contentstore.models import Schedule, MessageSet

logger = get_task_logger(__name__)


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
                str(len(messageset.messages.all()))
            # Build the schedule POST create object
            schedule = {
                "subscriptionId": str(subscription_id),
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
