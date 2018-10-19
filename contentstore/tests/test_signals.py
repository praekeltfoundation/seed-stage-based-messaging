"""
Unit tests for contentstore signals
"""
from django.test import TestCase
from unittest.mock import patch

from contentstore.models import Schedule
from seed_stage_based_messaging import test_utils as utils


class ScheduleSignalsTests(TestCase):
    """
    Tests for signals relating to the Schedule model
    """
    @patch('contentstore.tasks.SyncSchedule.scheduler')
    def test_schedule_created(self, scheduler):
        """
        When a schedule is created, then a corresponding schedule should be
        created in the scheduler service, and the ID of that schedule saved
        onto the model.
        """
        scheduler.create_schedule.return_value = {
            'id': '460fa767-2540-4ab7-bfce-e2cf54efdeb2',
        }
        schedule = Schedule.objects.create()

        scheduler.create_schedule.assert_called_once_with(
            schedule.scheduler_format)
        schedule.refresh_from_db()
        self.assertEqual(
            str(schedule.scheduler_schedule_id),
            '460fa767-2540-4ab7-bfce-e2cf54efdeb2')

    @patch('contentstore.tasks.SyncSchedule.scheduler')
    def test_schedule_modified(self, scheduler):
        """
        When a schedule is modified, then the corresponding schedule should be
        updated in the scheduler service.
        """
        scheduler.create_schedule.return_value = {
            'id': '460fa767-2540-4ab7-bfce-e2cf54efdeb2',
        }
        schedule = Schedule.objects.create()
        schedule.refresh_from_db()
        schedule.day_of_week = '1'
        schedule.save()

        scheduler.update_schedule.assert_called_with(
            '460fa767-2540-4ab7-bfce-e2cf54efdeb2', schedule.scheduler_format)

    @patch('contentstore.tasks.DeactivateSchedule.scheduler')
    def test_schedule_deleted(self, scheduler):
        """
        When a schedule is deleted, then the corresponding schedule should be
        deactivated in the scheduler service.
        """
        utils.disable_signals()
        schedule = Schedule.objects.create()
        schedule.scheduler_schedule_id = '460fa767-2540-4ab7-bfce-e2cf54efdeb2'
        schedule.save()
        utils.enable_signals()
        schedule.delete()

        scheduler.update_schedule.assert_called_with(
            '460fa767-2540-4ab7-bfce-e2cf54efdeb2', {'active': False})
