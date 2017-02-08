from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone

from subscriptions.models import Subscription
from subscriptions.tasks import send_next_message


class Command(BaseCommand):
    help = ("Fast forward subscriptions by one message if it is behind "
            "schedule or fast forward to end date. This is used when the "
            "messages sending failed to get the subscription up to date. Leave"
            " end_date blank for current date. Include `--action fast_forward`"
            " to fast forward them to the end date or `--action send` to send "
            "messages")

    def add_arguments(self, parser):
        parser.add_argument(
            "--end_date", dest="end_date", default=datetime.now(),
            type=lambda today: datetime.strptime(today, '%Y%m%d'),
            help='''Fast forward subscription to end_date
                  By default it will use datetime.now() (format YYYYMMDD)'''
        )
        parser.add_argument(
            "--action", dest="action", default=False,
            help=("Set to `send` to send next message or `fast_forward` to "
                  "fast forward the subscription."))
        parser.add_argument(
            "--verbose", dest="verbose", default=False,
            help=("Print out some details on the relevant subscriptions."))

    def handle(self, *args, **options):
        action = options['action']
        verbose = options['verbose']
        end_date = options['end_date']
        end_date = end_date.replace(tzinfo=timezone.utc)

        behind = 0
        forwards = 0
        sends = 0

        subscriptions = Subscription.objects.filter(active=True,
                                                    process_status=0)

        for sub in subscriptions:
            number, complete = sub.get_expected_next_sequence_number(end_date)

            if number > sub.next_sequence_number:

                if verbose:
                    self.stdout.write("{}: {}".format(sub.id, number -
                                      sub.next_sequence_number))

                if action == 'fast_forward':
                    updates = Subscription.fast_forward_lifecycle(sub,
                                                                  end_date)
                    forwards += len(updates) - 1
                elif action == 'send':
                    send_next_message.apply_async(args=[str(sub.id)])
                    sends += 1

                behind += 1

        self.stdout.write("%s subscription%s behind schedule."
                          % (behind, '' if behind == 1 else 's'))
        self.stdout.write("%s subscription%s fast forwarded to end date."
                          % (forwards, '' if forwards == 1 else 's'))
        self.stdout.write("Message sent to %s subscription%s."
                          % (sends, '' if sends == 1 else 's'))
