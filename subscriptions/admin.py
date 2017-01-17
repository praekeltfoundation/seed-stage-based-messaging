from django.contrib import admin

from .models import Subscription


class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'identity', 'messageset', 'next_sequence_number', 'lang',
        'active', 'completed', 'process_status', 'created_at', 'updated_at',)
    list_filter = (
        'messageset', 'lang', 'active', 'completed', 'process_status',
        'created_at', 'updated_at', )
    search_fields = ['id', 'identity']


admin.site.register(Subscription, SubscriptionAdmin)
