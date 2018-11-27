from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path

from .models import BehindSubscription, Subscription
from subscriptions.tasks import find_behind_subscriptions


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

    def get_urls(self):
        urls = super().get_urls()
        return urls + [path(
            "find_behind_subscriptions",
            self.admin_site.admin_view(self.find_behind_subscriptions),
            name="find_behind_subscriptions")]

    def find_behind_subscriptions(self, request):
        if not request.user.has_perm(
                "subscriptions.can_find_behind_subscriptions"):
            self.message_user(
                request,
                "You do not have permission to find behind subscriptions",
                level=messages.ERROR)
        else:
            task = find_behind_subscriptions.delay()
            self.message_user(
                request,
                "Find behind subscriptions task {} queued".format(task)
            )
        return redirect("admin:subscriptions_behindsubscription_changelist")
