from django.contrib import admin
from django.contrib import messages
from django.shortcuts import render
from django import forms

from .models import Schedule, MessageSet, Message, BinaryContent


class CloneMessageSetForm(forms.Form):
    short_name = forms.CharField(label='New short name', required=True)

    def clean_short_name(self):
        short_name = self.cleaned_data['short_name']
        if MessageSet.objects.filter(short_name=short_name).exists():
            raise forms.ValidationError(
                'A message set already exists with this name.')
        return short_name


class MessageSetAdmin(admin.ModelAdmin):

    actions = ['clone_messageset']

    def clone_messageset(self, request, queryset):
        if queryset.count() > 1:
            self.message_user(
                request, 'Only 1 message set can be cloned at a time.',
                level=messages.WARNING)
            return

        original = queryset.first()
        if 'do_action' in request.POST:
            form = CloneMessageSetForm(request.POST)
            if form.is_valid():
                new_short_name = form.cleaned_data['short_name']

                # NOTE: setting the PK to `None` results in a new record being
                # #     created
                clone = queryset.first()
                clone.pk = None
                clone.short_name = new_short_name
                clone.save()

                for cloned_message in original.messages.all():
                    cloned_message.pk = None
                    cloned_message.messageset = clone
                    cloned_message.save()

                self.message_user(request, 'Cloned the message set')
                return
        else:
            form = CloneMessageSetForm()

        return render(
            request, 'contentstore/messageset/clone_messageset.html',
            {
                'title': u'Clone message set: %s' % (original,),
                'object': original,
                'form': form,
            })
    clone_messageset.short_description = 'Clone selected message set'


admin.site.register(Schedule)
admin.site.register(MessageSet, MessageSetAdmin)
admin.site.register(Message)
admin.site.register(BinaryContent)
