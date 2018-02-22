from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand

from subscriptions.models import Subscription


class Command(BaseCommand):
    help = ("Active subscription holders need to be informed via audio file "
            "about the new missed call service.")

    def handle(self, *args, **options):
        self.stdout.write("Processing active subscriptions ...")
        count = 0
        try:
            active_subscriptions_list = list(
                Subscription.objects.filter(active=True))
        except ObjectDoesNotExist:
            self.stdout.write("No active subscriptions found")
        if len(active_subscriptions_list) > 0:
            for active_subscription in active_subscriptions_list:
                # Add audio file to subscription meta_data. Not sure how we'll
                # handle translations here.
                if (active_subscription.metadata is not None and
                        "welcome_message" not in active_subscription.metadata):
                    active_subscription["audio_file_url"] = "audio_file_url"
                    count += 1
        if count > 0:
            self.stdout.write(
                "Update {} subscriptions with voice notes".format(count))
        else:
            self.stdout.write(
                "No subscriptions updated with audio file notes")
