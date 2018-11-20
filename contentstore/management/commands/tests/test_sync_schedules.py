from six import StringIO
from django.core.management import call_command
from django.test import TestCase
from unittest.mock import patch

from contentstore.models import Schedule
from seed_stage_based_messaging import test_utils as utils


class SyncSchedulesTests(TestCase):
    @patch('contentstore.management.commands.sync_schedules.sync_schedule')
    def test_schedule_sync_called(self, sync_task):
        """
        The sync schedules management command should call the sync schedule
        task for every schedule.
        """
        utils.disable_signals()
        schedule = Schedule.objects.create()
        utils.enable_signals()

        out = StringIO()
        call_command('sync_schedules', stdout=out)

        sync_task.assert_called_once_with(str(schedule.id))
        self.assertIn(str(schedule.id), out.getvalue())
        self.assertIn('Synchronised 1 schedule/s', out.getvalue())
