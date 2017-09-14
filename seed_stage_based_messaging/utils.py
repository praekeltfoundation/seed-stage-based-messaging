import random
import re
from django.conf import settings
from contentstore.models import MessageSet
from subscriptions.models import Subscription
from seed_services_client import IdentityStoreApiClient

NORMALISE_METRIC_RE = re.compile(r'\W+')

identity_store_client = IdentityStoreApiClient(
    settings.IDENTITY_STORE_TOKEN,
    settings.IDENTITY_STORE_URL,
    retries=5,
    timeout=settings.DEFAULT_REQUEST_TIMEOUT,
)


def get_identity(identity_uuid):
    return identity_store_client.get_identity(identity_uuid)


def normalise_metric_name(name):
    """
    Replaces all non-alphanumeric characters with underscores.
    """
    return NORMALISE_METRIC_RE.sub('_', name).rstrip('_').lstrip('_')


def get_identity_address(identity_uuid, use_communicate_through=False):
    params = {"default": True}
    if use_communicate_through:
        params['use_communicate_through'] = True

    return identity_store_client.get_identity_address(
        identity_uuid, params=params)


def get_available_metrics():
    available_metrics = []
    available_metrics.extend(settings.METRICS_REALTIME)
    available_metrics.extend(settings.METRICS_SCHEDULED)

    messagesets = MessageSet.objects.all()
    for messageset in messagesets:
        messageset_name = normalise_metric_name(messageset.short_name)
        available_metrics.append(
            "subscriptions.%s.active.last" % messageset.short_name)
        available_metrics.append(
            "subscriptions.message_set.{}.sum".format(messageset_name))
        available_metrics.append(
            "subscriptions.message_set.{}.total.last".format(messageset_name))

    languages = Subscription.objects.order_by('lang').distinct('lang')\
        .values_list('lang', flat=True)
    for lang in languages:
        lang_normal = normalise_metric_name(lang)
        available_metrics.append(
            "subscriptions.language.{}.sum".format(lang_normal))
        available_metrics.append(
            "subscriptions.language.{}.total.last".format(lang_normal))

    content_types = MessageSet._meta.get_field('content_type').choices
    for content_type in content_types:
        type_normal = normalise_metric_name(content_type[0])
        available_metrics.append(
            "subscriptions.message_format.{}.sum".format(type_normal))
        available_metrics.append(
            "subscriptions.message_format.{}.total.last".format(type_normal))
        available_metrics.append(
            "message.{}.sum".format(type_normal))

        for messageset in messagesets:
            messageset_name = normalise_metric_name(messageset.short_name)
            available_metrics.append(
                "message.{}.{}.sum".format(type_normal, messageset_name))

    return available_metrics


def calculate_retry_delay(attempt, max_delay=300):
    """Calculates an exponential backoff for retry attempts with a small
    amount of jitter."""
    delay = int(random.uniform(2, 4) ** attempt)
    if delay > max_delay:
        # After reaching the max delay, stop using expontential growth
        # and keep the delay nearby the max.
        delay = int(random.uniform(max_delay - 20, max_delay + 20))
    return delay
