from django.core.management.base import BaseCommand, CommandError

from subscriptions.models import Subscription


class Command(BaseCommand):
    help = ("A command to add subscription metadata in order to "
            " inform subscribers of new or changed features.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--audio-file',
            type=str,
            help='A path to the audio file containing the "\
            "notification message'
        )

    def handle(self, *args, **options):
        with open('options.txt', 'w') as f:
            for key in options.keys():
                f.write(key + '\n')

        audio_file = options['--audio-file']
        if not audio_file:
            raise CommandError('--audio-file is a required parameter')
        self.stdout.write("Processing active subscriptions ...")
        count = 0
        active_subscriptions = Subscription.objects.filter(
            active=True,
            messageset__content_type="audio")
        for active_subscription in active_subscriptions.iterator():
            # Add audio file to subscription meta_data. Not sure how we'll
            # handle translations here.
            if (active_subscription.metadata.get("prepend_next_delivery")
                    is None):
                active_subscription.metadata["prepend_next_delivery"] = \
                    audio_file.replace('<LANG>', active_subscription.lang)
                count += 1
        if count > 0:
            self.stdout.write("Updated {} subscriptions with audio "
                              "notifications".format(count))
        else:
            self.stdout.write(
                "No subscriptions updated with audio file notes")
