from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
import json

from subscriptions.models import Subscription
from subscriptions.tasks import send_next_message


class Command(BaseCommand):
    help = ("This command is used when the subscription has fallen behind "
            "schedule. Leave the action argument blank to see how many "
            "subscriptions are behind. Running the command with `--action "
            "send` will send a message to each subscription that is behind. "
            "Running the command with `--action fast_forward` will fast "
            "forward the subscriptions that are behind to the end_date. "
            "Running the command with `--action diff` will print out the "
            "differences that running the command would make.")

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
                  "fast forward the subscription or `diff` to print out the "
                  "changes that the command would make."))
        parser.add_argument(
            "--verbose", dest="verbose", default=False,
            help=("Print out some details on the relevant subscriptions."))
        parser.add_argument(
            "--message-set", dest="message_set", default=None, type=int,
            help=("Only apply the action to the subscriptions that are for "
                  "the specified message set, defaults to all message sets."))
        parser.add_argument(
            "--messages-limit", dest="messages_limit", default=None, type=int,
            help=("Only apply the action to subscriptions that are behind by"
                  "the limit or less than the limit. Defaults to no limit.")
        )

    def handle(self, *args, **options):
        action = options['action']
        verbose = options['verbose']
        end_date = options['end_date']
        end_date = end_date.replace(tzinfo=timezone.utc)
        message_set = options['message_set']
        messages_limit = options['messages_limit']

        behind = 0
        forwards = 0
        sends = 0

        subscriptions = Subscription.objects.filter(active=True,
                                                    process_status=0)
        if message_set is not None:
            subscriptions = subscriptions.filter(messageset__pk=message_set)

        for sub in subscriptions.iterator():
            number, complete = sub.get_expected_next_sequence_number(end_date)

            if (
                    messages_limit is not None and
                    number - sub.next_sequence_number > messages_limit):
                continue

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
                elif action == 'diff':
                    start_ms = sub.messageset.pk
                    start_nseq = sub.next_sequence_number
                    subs = Subscription.fast_forward_lifecycle(
                        sub, end_date, save=False)
                    end_sub = subs[-1]
                    self.stdout.write(json.dumps({
                        "language": sub.lang,
                        "identity": sub.identity,
                        "current_messageset_id": start_ms,
                        "current_sequence_number": start_nseq,
                        "expected_messageset_id": end_sub.messageset.pk,
                        "expected_sequence_number":
                            end_sub.next_sequence_number,
                    }))

                behind += 1

        self.stdout.write("%s subscription%s behind schedule."
                          % (behind, '' if behind == 1 else 's'))
        self.stdout.write("%s subscription%s fast forwarded to end date."
                          % (forwards, '' if forwards == 1 else 's'))
        self.stdout.write("Message sent to %s subscription%s."
                          % (sends, '' if sends == 1 else 's'))
