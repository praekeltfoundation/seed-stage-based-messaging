from django.core.management.base import BaseCommand
from django.forms.models import model_to_dict

from subscriptions.models import Subscription


class Command(BaseCommand):
    help = ("A command to add subscription metadata in order to "
            " inform subscribers of new or changed features.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--audio-file',
            dest="audio_file",
            type=str,
            required=True,
            help='A path to the audio file containing the "\
            "notification message'
        )
        parser.add_argument(
            '--message-set',
            dest="message_set",
            type=str,
            help='A string to filter the messagesets by name, only update '
            'subscriptions linked to these.'
        )

    def handle(self, *args, **options):
        audio_file = options['audio_file']
        message_set = options['message_set']

        active_subscriptions = Subscription.objects.filter(
            active=True,
            messageset__content_type="audio")

        if message_set:
            active_subscriptions = active_subscriptions.filter(
                messageset__short_name__contains=message_set)

        count = 0
        for active_subscription in active_subscriptions.iterator():

            if not active_subscription.metadata:
                active_subscription.metadata = {}

            if (active_subscription.metadata.get("prepend_next_delivery")
                    is not None):
                continue

            active_subscription.metadata["prepend_next_delivery"] = \
                audio_file.format(**model_to_dict(active_subscription))
            active_subscription.save()

            count += 1

        self.success(
            "Updated {} subscription(s) with audio notifications.".format(
                count))

    def log(self, level, msg):
        self.stdout.write(level(msg))

    def success(self, msg):
        self.log(self.style.SUCCESS, msg)
