from django.contrib import admin

from .models import Schedule, MessageSet, Message, BinaryContent

admin.site.register(Schedule)
admin.site.register(MessageSet)
admin.site.register(Message)
admin.site.register(BinaryContent)
