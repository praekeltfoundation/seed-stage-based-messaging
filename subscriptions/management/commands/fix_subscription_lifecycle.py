from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone

from subscriptions.models import Subscription
from subscriptions.tasks import send_next_message


class Command(BaseCommand):
    help = ("Fast forward subscriptions by one message if it is behind "
            "schedule. This is used when the messages sending failed to get "
            "the subscription up to date. Leave end_date blank for current "
            "date. Include `--fix True` to update and send messages")

    def add_arguments(self, parser):
        parser.add_argument(
            "--end_date", dest="end_date", default=datetime.now(),
            type=lambda today: datetime.strptime(today, '%Y%m%d'),
            help='''Fast forward subscription to end_date
                  By default it will use datetime.now() (format YYYYMMDD)'''
        )
        parser.add_argument(
            "--fix", dest="update", default=False,
            help=("Set to True to update and send message."))

    def handle(self, *args, **options):
        update = options['update']
        end_date = options['end_date']
        end_date = end_date.replace(tzinfo=timezone.utc)

        updated = 0

        subscriptions = Subscription.objects.filter(active=True,
                                                    process_status=0)

        for sub in subscriptions:
            number, complete = sub.get_expected_next_sequence_number(end_date)

            if number > sub.next_sequence_number:
                if update:
                    send_next_message.apply_async(args=[str(sub.id)])

                updated += 1

        self.stdout.write("Message sent to %s subscription%s."
                          % (updated, '' if updated == 1 else 's'))
        if not update:
            self.stdout.write("ONLY A TEST RUN, NOTHING WAS UPDATED/SENT\n"
                              "Add this to update/send: `--fix True`")
