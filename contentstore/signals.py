"""
Contains the singal handlers for contentstore
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from contentstore.models import Schedule


@receiver(post_save, sender=Schedule)
def schedule_saved(sender, instance, **kwargs):
    """
    Fires off the celery task to ensure that this schedule is in the scheduler

    Arguments:
        sender {class} -- The model class, always Schedule
        instance {Schedule} --
            The instance of the Schedule that we want to sync
    """
    from contentstore.tasks import sync_schedule
    sync_schedule.delay(str(instance.id))


@receiver(post_delete, sender=Schedule)
def schedule_deleted(sender, instance, **kwargs):
    """
    Fires off the celery task to ensure that this schedule is deactivated

    Arguments:
        sender {class} -- The model class, always Schedule
        instance {Schedule} --
            The instance of the schedule that we want to deactivate
    """
    from contentstore.tasks import deactivate_schedule
    deactivate_schedule.delay(str(instance.scheduler_schedule_id))
