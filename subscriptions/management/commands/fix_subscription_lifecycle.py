from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone

from subscriptions.models import Subscription


class Command(BaseCommand):
    help = ("Fast forward subscriptions lifecycle up to given date. This "
            "is used when the messages sending failed to get the subscription "
            "up to date. Leave end_date blank for current date")

    def add_arguments(self, parser):
        parser.add_argument(
            "--end_date", dest="end_date", default=datetime.now(),
            type=lambda today: datetime.strptime(today, '%Y%m%d'),
            help='''Fast forward subscription to end_date
                  By default it will use datetime.now() (format YYYYMMDD)'''
        )

    def handle(self, *args, **options):
        end_date = options['end_date']
        end_date = end_date.replace(tzinfo=timezone.utc)

        updated = 0

        subscriptions = Subscription.objects.filter(active=True)

        for sub in subscriptions:
            updates = Subscription.fast_forward_lifecycle(sub, end_date)
            updated += len(updates) - 1

        self.stdout.write("%s subscription%s updated."
                          % (updated, '' if updated == 1 else 's'))
