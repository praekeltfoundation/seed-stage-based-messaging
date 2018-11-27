import uuid

from datetime import timedelta

from django.contrib.postgres.fields import JSONField
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
                                   null=False, on_delete=models.PROTECT)
    initial_sequence_number = models.IntegerField(default=1, null=False,
                                                  blank=False)
    next_sequence_number = models.IntegerField(default=1, null=False,
                                               blank=False)
    lang = models.CharField(max_length=6, null=False, blank=False)
    active = models.BooleanField(default=True)
    completed = models.BooleanField(default=False)
    schedule = models.ForeignKey(Schedule, related_name='subscriptions',
                                 null=False, on_delete=models.PROTECT)
    process_status = models.IntegerField(default=0, null=False, blank=False)
    metadata = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, related_name='subscriptions_created',
                                   null=True, on_delete=models.SET_NULL)
    updated_by = models.ForeignKey(User, related_name='subscriptions_updated',
                                   null=True, on_delete=models.SET_NULL)
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


@receiver(post_save, sender=Subscription)
def fire_metrics_if_new(sender, instance, created, **kwargs):
    from .tasks import fire_metric
    if created:
        fire_metric.apply_async(kwargs={
            "metric_name": 'subscriptions.created.sum',
            "metric_value": 1.0
        })


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
                                   null=False, on_delete=models.CASCADE)
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
                                null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return '{}: {}'.format(self.id, self.received_at)


class BehindSubscription(models.Model):
    """
    Subscriptions that are behind where they should be. Filled out by
    subscriptions.tasks.find_behind_subscriptions
    """
    subscription = models.ForeignKey(
        to=Subscription, on_delete=models.CASCADE,
        help_text="The subscription that is behind",
    )
    messages_behind = models.IntegerField(
        help_text="The number of messages the subscription is behind by"
    )
    current_messageset = models.ForeignKey(
        to=MessageSet, on_delete=models.CASCADE, related_name="+",
        help_text="The message set the the subscription is on",
    )
    current_sequence_number = models.IntegerField(
        help_text="Which sequence in the messageset we are at",
    )
    expected_messageset = models.ForeignKey(
        to=MessageSet, on_delete=models.CASCADE, related_name="+",
        help_text="The messageset that the subscription should be on",
    )
    expected_sequence_number = models.IntegerField(
        help_text="Which sequence in the messageset we expect to be",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = (
            ("can_find_behind_subscriptions", "Can find behind subscriptions"),
        )
