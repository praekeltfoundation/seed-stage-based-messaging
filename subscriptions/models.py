import uuid

from django.contrib.postgres.fields import JSONField
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils.encoding import python_2_unicode_compatible

from contentstore.models import MessageSet, Schedule


@python_2_unicode_compatible
class Subscription(models.Model):

    """ Identity subscriptions and their status
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.CharField(max_length=36, null=False, blank=False)
    version = models.IntegerField(default=1)
    messageset = models.ForeignKey(MessageSet, related_name='subscriptions',
                                   null=False)
    next_sequence_number = models.IntegerField(default=1, null=False,
                                               blank=False)
    lang = models.CharField(max_length=6, null=False, blank=False)
    active = models.BooleanField(default=True)
    completed = models.BooleanField(default=False)
    schedule = models.ForeignKey(Schedule, related_name='subscriptions',
                                 null=False)
    process_status = models.IntegerField(default=0, null=False, blank=False)
    metadata = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, related_name='subscriptions_created',
                                   null=True)
    updated_by = models.ForeignKey(User, related_name='subscriptions_updated',
                                   null=True)
    user = property(lambda self: self.created_by)

    def get_scheduler_id(self):
        return self.metadata.get("scheduler_schedule_id")

    def __str__(self):
        return str(self.id)


# Make sure new subscriptions are created on scheduler
@receiver(post_save, sender=Subscription)
def fire_sub_action_if_new(sender, instance, created, **kwargs):
    from .tasks import schedule_create
    if created:
        schedule_create.apply_async(args=[str(instance.id)])


# Deactivate the schedule for this subscription when completed
@receiver(post_save, sender=Subscription)
def disable_schedule_if_complete(sender, instance, created, **kwargs):
    from .tasks import schedule_disable
    if instance.completed is True or instance.process_status == 2:
        schedule_disable.apply_async(args=[str(instance.id)])


# Deactivate the schedule for this subscription when deactivated
@receiver(post_save, sender=Subscription)
def disable_schedule_if_deactivated(sender, instance, created, **kwargs):
    from .tasks import schedule_disable
    if instance.active is False:
        schedule_disable.apply_async(args=[str(instance.id)])


@receiver(post_save, sender=Subscription)
def fire_metrics_if_new(sender, instance, created, **kwargs):
    from .tasks import fire_metric
    if created:
        fire_metric.apply_async(kwargs={
            "metric_name": 'subscriptions.created.sum',
            "metric_value": 1.0
        })


@receiver(post_save, sender=Subscription)
def fire_metric_per_message_set(sender, instance, created, **kwargs):
    """
    Fires metrics according to the message set of the subscription.
    """
    from .tasks import fire_metric
    from seed_stage_based_messaging.utils import normalise_metric_name
    if created:
        ms_name = normalise_metric_name(instance.messageset.short_name)
        fire_metric.apply_async(kwargs={
            "metric_name":
                "subscriptions.message_set.{}.sum".format(ms_name),
            "metric_value": 1.0,
        })

        total_key = 'subscriptions.message_set.{}.total.last'.format(ms_name)
        total = get_or_incr_cache(
            total_key,
            Subscription.objects.filter(
                messageset=instance.messageset).count)
        fire_metric.apply_async(kwargs={
            "metric_name": total_key,
            "metric_value": total,
        })


@receiver(post_save, sender=Subscription)
def fire_metric_per_lang(sender, instance, created, **kwargs):
    """
    Fires metrics according to the language of the subscription.
    """
    from .tasks import fire_metric
    from seed_stage_based_messaging.utils import normalise_metric_name
    if created:
        lang = normalise_metric_name(instance.lang)
        fire_metric.apply_async(kwargs={
            "metric_name": "subscriptions.language.{}.sum".format(lang),
            "metric_value": 1.0,
        })

        total_key = 'subscriptions.language.{}.total.last'.format(lang)
        total = get_or_incr_cache(
            total_key,
            Subscription.objects.filter(
                lang=lang).count)
        fire_metric.apply_async(kwargs={
            "metric_name": total_key,
            "metric_value": total,
        })


def get_or_incr_cache(key, func):
    """
    Used to either get and increment a value from the cache, or if the value
    doesn't exist in the cache, run the function to get a value to use to
    populate the cache
    """
    value = cache.get(key)
    if value is None:
        value = func()
        cache.set(key, value)
    else:
        cache.incr(key)
        value += 1
    return value
