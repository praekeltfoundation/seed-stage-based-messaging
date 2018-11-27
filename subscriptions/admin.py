from django.contrib import admin

from .models import BehindSubscription, Subscription


class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'identity', 'messageset', 'next_sequence_number', 'lang',
        'active', 'completed', 'process_status', 'created_at', 'updated_at',)
    list_filter = (
        'messageset', 'lang', 'active', 'completed', 'process_status',
        'created_at', 'updated_at', )
    search_fields = ['id', 'identity']


admin.site.register(Subscription, SubscriptionAdmin)


@admin.register(BehindSubscription)
class BehindSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("subscription", "messages_behind", "created_at")
    list_filter = ("messages_behind", "current_messageset")
    list_select_related = ("current_messageset", "subscription")
    raw_id_fields = ("subscription",)
    readonly_fields = ("created_at",)
