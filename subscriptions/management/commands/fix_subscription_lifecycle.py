from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone

from subscriptions.models import Subscription
from subscriptions.tasks import send_next_message


class Command(BaseCommand):
    help = ("This command is used when the subscription has fallen behind "
            "schedule. Leave the action argument blank to see how many "
            "subscriptions are behind. Running the command with `--action "
            "send` will send a message to each subscription that is behind. "
            "Running the command with `--action fast_forward` will fast "
            "forward the subscriptions that are behind to the end_date.")

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
                    Subscription.fast_forward_lifecycle(sub, end_date)
                    forwards += 1
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
