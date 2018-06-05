from django.core.management.base import BaseCommand

from contentstore.models import Schedule
from contentstore.tasks import sync_schedule


class Command(BaseCommand):
    help = "Synchronises all schedules with the scheduler"

    def handle(self, *args, **kwargs):
        count = 0
        self.stdout.write('Fetching schedules...')

        for schedule in Schedule.objects.all().iterator():
            self.stdout.write('Synchronising schedule {}'.format(schedule.id))
            sync_schedule(str(schedule.id))
            count += 1

        self.stdout.write(self.style.SUCCESS(
            'Synchronised {} schedule/s'.format(count)))
