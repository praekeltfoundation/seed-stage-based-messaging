from django.core.management.base import BaseCommand, CommandError

from subscriptions.models import Subscription


class Command(BaseCommand):
    help = ("Active subscription holders need to be informed via audio file "
            "about the new missed call service.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--audio', type=str,
            help='Audio file containing the notification of the new missed'
            ' call service.')

    def handle(self, *args, **options):
        audio_file = options['audio']
        if not audio_file:
            raise CommandError('--audio_file is a required parameter')
        self.stdout.write("Processing active subscriptions ...")
        count = 0
        active_subscriptions = Subscription.objects.filter(
            active=True,
            messageset__content_type="audio")
        for active_subscription in active_subscriptions.iterator():
            # Add audio file to subscription meta_data. Not sure how we'll
            # handle translations here.
            if (not active_subscription.metadata["prepend_next_delivery"] or
                    active_subscription.metadata["prepend_next_delivery"]
                    is None):
                active_subscription.metadata["prepend_next_delivery"] = \
                    audio_file
                count += 1
        if count > 0:
            self.stdout.write("Updated {} subscriptions with audio "
                              "notifications".format(count))
        else:
            self.stdout.write(
                "No subscriptions updated with audio file notes")
