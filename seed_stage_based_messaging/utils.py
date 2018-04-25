import random
import re
from django.conf import settings
from contentstore.models import MessageSet
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

    for messageset in MessageSet.objects.all().iterator():
        send_type = normalise_metric_name(messageset.content_type)
        ms_name = normalise_metric_name(messageset.short_name)
        available_metrics.append(
            'message.{}.{}.sum'.format(send_type, ms_name))
        available_metrics.append(
            'message.{}.sum'.format(send_type))

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
