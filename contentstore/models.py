import os.path
from django.db import models
from rest_framework.serializers import ValidationError
from django.utils.translation import ugettext_lazy as _
from datetime import datetime


class Schedule(models.Model):

    """
    Schedules (sometimes referred to as Protocols) are the method used to
    define the rate and frequency at which the messages are sent to
    the recipient
    """
    minute = models.CharField(_('minute'), max_length=64, default='*')
    hour = models.CharField(_('hour'), max_length=64, default='*')
    day_of_week = models.CharField(
        _('day of week'), max_length=64, default='*',
    )
    day_of_month = models.CharField(
        _('day of month'), max_length=64, default='*',
    )
    month_of_year = models.CharField(
        _('month of year'), max_length=64, default='*',
    )

    class Meta:
        verbose_name = _('schedule')
        verbose_name_plural = _('schedules')
        ordering = ['month_of_year', 'day_of_month',
                    'day_of_week', 'hour', 'minute']

    def __unicode__(self):
        rfield = lambda f: f and str(f).replace(' ', '') or '*'
        return u'{0} {1} {2} {3} {4} (m/h/d/dM/MY)'.format(
            rfield(self.minute), rfield(self.hour), rfield(self.day_of_week),
            rfield(self.day_of_month), rfield(self.month_of_year),
        )


class MessageSet(models.Model):

    """
        Details about a set of messages that a recipient can be sent on
        a particular schedule
    """
    short_name = models.CharField(_('Short name'), max_length=20, unique=True)
    notes = models.TextField(_('Notes'), null=True, blank=True)
    next_set = models.ForeignKey('self',
                                 null=True,
                                 blank=True)
    default_schedule = models.ForeignKey(Schedule,
                                         related_name='message_sets',
                                         null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return u"%s" % self.short_name


def generate_new_filename(instance, filename):
    ext = os.path.splitext(filename)[-1]  # get file extension
    return "%s%s" % (datetime.now().strftime("%Y%m%d%H%M%S%f"), ext)


class BinaryContent(models.Model):
    """
        File store for reference in messages. Storage method handle by
        settings file.
    """

    content = models.FileField(upload_to=generate_new_filename,
                               max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return u"%s" % (self.content.path.split('/')[-1])


class Message(models.Model):

    """
        Messages that a recipient can be sent
    """
    messageset = models.ForeignKey(MessageSet,
                                   related_name='messages',
                                   null=False)
    sequence_number = models.IntegerField(null=False, blank=False)
    lang = models.CharField(max_length=6, null=False, blank=False)
    text_content = models.TextField(null=True, blank=True)
    binary_content = models.ForeignKey(BinaryContent,
                                       related_name='message',
                                       null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sequence_number']

    def clean(self):
        # Don't allow messages to have neither a text or binary content
        if any([self.text_content, self.binary_content]) is False:
            raise ValidationError(
                _('Messages must have text or file attached'))

    def save(self, *args, **kwargs):
        self.clean()
        super(Message, self).save(*args, **kwargs)

    def __unicode__(self):
        return _("Message %s in %s from %s") % (
            self.sequence_number, self.lang, self.messageset.short_name)
