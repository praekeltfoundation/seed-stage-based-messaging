import uuid

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class Subscription(models.Model):

    """ Contacts subscriptions and their status
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.CharField(max_length=36, null=False, blank=False)
    version = models.IntegerField(default=1)
    messageset_id = models.IntegerField(null=False, blank=False)
    next_sequence_number = models.IntegerField(default=1, null=False,
                                               blank=False)
    lang = models.CharField(max_length=6, null=False, blank=False)
    active = models.BooleanField(default=True)
    completed = models.BooleanField(default=False)
    schedule = models.IntegerField(default=1)
    process_status = models.IntegerField(default=0, null=False, blank=False)
    metadata = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, related_name='registrations_created',
                                   null=True)
    updated_by = models.ForeignKey(User, related_name='registrations_updated',
                                   null=True)
    user = property(lambda self: self.created_by)

    def __str__(self):
        return str(self.id)


# Make sure new subscriptions are created on scheduler
@receiver(post_save, sender=Subscription)
def fire_sub_action_if_new(sender, instance, created, **kwargs):
    from .tasks import schedule_create
    if created:
        schedule_create.apply_async(args=[str(instance.id)])
