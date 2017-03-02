from django.core.management.base import BaseCommand
from django.core.validators import URLValidator
from django.conf import settings

from subscriptions.models import Subscription
from seed_services_client import SchedulerApiClient


def url_validator(url_str):
    URLValidator(url_str)
    return url_str


class Command(BaseCommand):
    help = 'Removes all duplicate subscriptions'

    DEFAULT_TIME_DELTA = 60
    DEFAULT_FIELDS = [
        'identity', 'version', 'messageset', 'lang', 'active',
        'completed', 'schedule']

    def add_arguments(self, parser):
        parser.add_argument(
            '--time-delta', action='store', dest='time_delta', type=int,
            nargs='?', default=self.DEFAULT_TIME_DELTA,
            help='The maximum time difference in seconds between two '
            'subscriptions for them to be considered duplicates.'
        )
        parser.add_argument(
            '--fields', action='store', dest='fields', type=str, nargs='+',
            default=self.DEFAULT_FIELDS,
            help='The fields to compare to determine if the subscriptions are'
            ' identical or not.'
        )
        parser.add_argument(
            '--fix', action='store_true', default=False,
            help=('Actually remove the duplicates instead of only listing'
                  'duplicates')
        )
        parser.add_argument(
            '--scheduler-url',
            type=url_validator,
            default=settings.SCHEDULER_URL,
            help='The scheduler url to use, defaults to settings.SCHEDULER_URL'
        )
        parser.add_argument(
            '--scheduler-token',
            type=str,
            default=settings.SCHEDULER_API_TOKEN,
            help=('The schedule API token, defaults to '
                  'settings.SCHEDULER_API_TOKEN')
        )

    def second_diff(self, d1, d2):
        '''
        Returns the difference, in seconds, between d1 and d2. The amount
        returned is always positive.
        '''
        return abs((d1 - d2).total_seconds())

    def is_within_limits(self, limit, date, dates):
        '''
        Returns True if the difference between date and any value in dates
        is less than or equal to limit.
        '''
        return any((self.second_diff(date, d) <= limit for d in dates))

    def handle(self, *args, **options):
        time_delta = options['time_delta']
        fields = options['fields']
        fix = options['fix']
        scheduler_token = options['scheduler_token']
        scheduler_url = options['scheduler_url']
        removed = 0

        scheduler_client = SchedulerApiClient(scheduler_token, scheduler_url)

        uniques = Subscription.objects.distinct(*fields)
        for unique in uniques:
            subscriptions = Subscription.objects.filter(**{
                field: getattr(unique, field) for field in fields}
            )
            subscriptions = subscriptions.filter(active=True, completed=False)
            subscriptions = subscriptions.order_by('created_at')
            if len(subscriptions) <= 1:
                continue
            dates = [subscriptions[0].created_at]
            for sub in subscriptions[1:]:
                if self.is_within_limits(time_delta, sub.created_at, dates):
                    if fix:
                        scheduler_id = sub.get_scheduler_id()
                        # NOTE: grabbing the signature of the sub before
                        #       deleting otherwise the warning below just
                        #       shows `None` as Django deletes the PK
                        #       after delete() is called
                        sub_str = str(sub)
                        sub.delete()
                        if scheduler_id:
                            scheduler_client.delete_schedule(scheduler_id)
                        else:
                            self.warning(
                                'Subscription %s has no scheduler_id.' % (
                                    sub_str,))
                    else:
                        self.warning(
                            'Not removing %s, use --fix to actually remove.' %
                            (sub,))

                    removed += 1
                dates.append(sub.created_at)

        self.success('Removed %d duplicate subscriptions.' % (removed,))

    def log(self, level, msg):
        self.stdout.write(level(msg))

    def warning(self, msg):
        self.log(self.style.WARNING, msg)

    def success(self, msg):
        self.log(self.style.SUCCESS, msg)
