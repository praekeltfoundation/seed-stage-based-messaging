import uuid

from datetime import timedelta

from django.contrib.postgres.fields import JSONField
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils.encoding import python_2_unicode_compatible
from django.utils.timezone import now

from contentstore.models import MessageSet, Schedule, Message


@python_2_unicode_compatible
class Subscription(models.Model):

    """ Identity subscriptions and their status
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.CharField(
        max_length=36, null=False, blank=False, db_index=True)
    version = models.IntegerField(default=1)
    messageset = models.ForeignKey(MessageSet, related_name='subscriptions',
                                   null=False)
    initial_sequence_number = models.IntegerField(default=1, null=False,
                                                  blank=False)
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

    def get_expected_next_sequence_number(self, end_date=None):
        """Determines the expected next sequence number this subscription
        should be at based on the configured schedule, message set and
        creation date. It also checks if the subscription should be completed.

        Returns a tuple of next_sequence_number, completed.
        """
        if end_date is None:
            end_date = now()
        set_max = self.messageset.get_messageset_max(self.lang)
        runs = self.schedule.get_run_times_between(self.created_at, end_date)
        count = len(runs) + (self.initial_sequence_number - 1)
        if count >= set_max:
            return set_max, True
        else:
            expected = count + 1
            return expected, False

    @property
    def has_next_sequence_number(self):
        """Returns True if this Subscription has not yet reached the
        configured MessageSet's maximum sequence number, returns False
        otherwise.
        """
        return self.next_sequence_number < self.messageset.get_messageset_max(
            self.lang)

    def mark_as_complete(self, save=True):
        self.completed = True
        self.active = False
        self.process_status = 2  # Completed
        if save:
            self.save()

    def fast_forward(self, end_date=None, save=True):
        """Moves a subscription forward to where it should be based on the
        configured MessageSet and schedule and the given end_date (defaults
        to utcnow if not specified).

        Returns True if the subscription was completed due to this action,
        False otherwise.
        """
        number, complete = self.get_expected_next_sequence_number(end_date)
        if complete:
            self.mark_as_complete(save=save)

        self.next_sequence_number = number
        if save:
            self.save()

        return complete

    @classmethod
    def fast_forward_lifecycle(self, subscription, end_date=None, save=True):
        """Takes an existing Subscription object and fast forwards it through
        the entire lifecycle based on the given end_date. If no end_date is
        specified now will be used.

        This method will create all subsequent Subscription objects as required
        by the configured MessageSet object's next_set value.

        Returns a list of all Subscription objects operated on.
        """
        if end_date is None:
            end_date = now()

        subscriptions = [subscription]
        done = False
        sub = subscription
        while not done:
            completed = sub.fast_forward(end_date, save=save)
            if completed:
                if sub.messageset.next_set:
                    # If the sub.lang is None or empty there is a problem with
                    # the data that we can't directly resolve here so we
                    # guard against that breaking things here.
                    if not sub.lang:
                        # TODO: what do we do here?
                        break

                    run_dates = sub.messageset.get_all_run_dates(
                        sub.created_at,
                        sub.lang,
                        sub.schedule,
                        sub.initial_sequence_number
                    )
                    if run_dates:
                        last_date = run_dates.pop()
                        newsub = Subscription(
                            identity=sub.identity,
                            lang=sub.lang,
                            messageset=sub.messageset.next_set,
                            schedule=sub.messageset.next_set.default_schedule
                        )
                        if save:
                            newsub.save()
                        # Because created_at uses auto_now we have to set the
                        # created date manually after creation. Add a minute to
                        # the expected last run date because in the normal flow
                        # new subscriptions are processed after the day's send
                        # has been completed.
                        newsub.created_at = last_date + timedelta(minutes=1)
                        completed = newsub.fast_forward(end_date, save=save)
                        subscriptions.append(newsub)
                        sub = newsub
                    else:
                        # This subscription is new and hasn't had any runs yet
                        done = True
                else:
                    # There are no more subscriptions in this lifecycle.
                    done = True
            else:
                # The subscription isn't completed yet.
                done = True

        return subscriptions

    @property
    def is_ready_for_processing(self):
        return self.process_status == 0 and \
               self.completed is not True and \
               self.active is True


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
                lang=instance.lang).count)
        fire_metric.apply_async(kwargs={
            "metric_name": total_key,
            "metric_value": total,
        })


@receiver(post_save, sender=Subscription)
def fire_metric_per_message_format(sender, instance, created, **kwargs):
    """
    Fires metrics according to the content type of the subscription.
    """
    from .tasks import fire_metric
    from seed_stage_based_messaging.utils import normalise_metric_name
    if created:
        content_type = normalise_metric_name(instance.messageset.content_type)
        fire_metric.apply_async(kwargs={
            "metric_name":
                "subscriptions.message_format.{}.sum".format(content_type),
            "metric_value": 1.0,
        })

        total_key = 'subscriptions.message_format.{}.total.last'.format(
            content_type)
        total = get_or_incr_cache(
            total_key,
            Subscription.objects.filter(
                messageset__content_type=instance.messageset.content_type
                ).count)

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


@python_2_unicode_compatible
class SubscriptionSendFailure(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    task_id = models.UUIDField()
    initiated_at = models.DateTimeField()
    reason = models.TextField()

    def __str__(self):  # __unicode__ on Python 2
        return str(self.id)


@python_2_unicode_compatible
class EstimatedSend(models.Model):

    """ Estimated number of messages to be sent per message set per day
    """
    send_date = models.DateField()
    messageset = models.ForeignKey(MessageSet, related_name='estimates',
                                   null=False)
    estimate_subscriptions = models.IntegerField(null=False, blank=False)
    estimate_identities = models.IntegerField(null=False, blank=False)

    class Meta:
        unique_together = (("send_date", "messageset"),)

    def __str__(self):
        return '{},{}:{}/{}'.format(
            self.send_date, self.messageset.short_name,
            self.estimate_subscriptions, self.estimate_identities)


@python_2_unicode_compatible
class ResendRequest(models.Model):

    """ Resend Request from user, used to trigger a resend.
    """
    received_at = models.DateTimeField(auto_now_add=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    outbound = models.UUIDField(null=True)
    message = models.ForeignKey(Message, related_name='resend_requests',
                                null=True)

    def __str__(self):
        return '{}: {}'.format(self.id, self.received_at)
