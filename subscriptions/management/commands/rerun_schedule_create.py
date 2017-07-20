import csv
import os

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError

from subscriptions.models import Subscription
from subscriptions.tasks import schedule_create


class Command(BaseCommand):
    help = ("Sometimes the task to create the schedule for a subscription "
            "fails. This takes a list of subscription ids and reruns the "
            "schedule creation task if they don't have a schedule.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv', type=str,
            help='CSV file containing the UUIDs of the subscriptions to check')

    def handle(self, *args, **options):
        file_name = options['csv']

        if not file_name:
            raise CommandError('--csv is a required parameter')
        if not os.path.isfile(file_name):
            raise CommandError('--csv must be a valid path to a file')

        self.stdout.write('Processing file ...')
        count = 0
        for sub_id in self.subscription_from_csv(file_name):
            try:
                subscription = Subscription.objects.get(pk=sub_id)
            except ObjectDoesNotExist:
                self.stdout.write("Subscription %s does not exist" % sub_id)
                continue
            except ValueError:
                self.stdout.write("%s is not a valid UUID" % sub_id)
                continue

            # Some schedules were created but failed before saving to the sub.
            # If it's been triggered it probably has a schedule so ignore
            if ((subscription.metadata is not None and
                    "scheduler_schedule_id" in subscription.metadata) or
                    subscription.next_sequence_number >
                    subscription.initial_sequence_number):
                self.stdout.write("Subscription %s already has schedule" %
                                  sub_id)
                continue
            else:
                result = schedule_create(sub_id)
                if not result:
                    self.stdout.write("Failed to create schedule for "
                                      "subscription %s" % sub_id)
                else:
                    count += 1
                    self.stdout.write("Created schedule %s for subscription %s"
                                      % (result, sub_id))
        self.stdout.write("Created %s schedules" % count)

    def subscription_from_csv(self, csv_file):
        with open(csv_file) as csv_file:
            reader = csv.DictReader(csv_file)
            if not (set(["subscription"]) <= set(reader.fieldnames)):
                raise CommandError("CSV file must contain subscription.")
            for data in reader:
                yield data["subscription"]
