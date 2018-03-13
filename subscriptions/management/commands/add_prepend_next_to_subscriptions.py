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

    def handle(self, *args, **options):
        audio_file = options['audio_file']

        active_subscriptions = Subscription.objects.filter(
            active=True,
            messageset__content_type="audio")

        count = 0
        for active_subscription in active_subscriptions.iterator():

            if (active_subscription.metadata.get("prepend_next_delivery")
                    is None):
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
