import re
import requests
from django.conf import settings
from contentstore.models import MessageSet
from subscriptions.models import Subscription


NORMALISE_METRIC_RE = re.compile(r'\W+')


def get_identity(identity_uuid):
    url = "%s/%s/%s/" % (settings.IDENTITY_STORE_URL, "identities",
                         identity_uuid)
    headers = {
        'Authorization': 'Token %s' % settings.IDENTITY_STORE_TOKEN,
        'Content-Type': 'application/json'
    }
    r = requests.get(url, headers=headers)
    return r.json()


def normalise_metric_name(name):
    """
    Replaces all non-alphanumeric characters with underscores.
    """
    return NORMALISE_METRIC_RE.sub('_', name).rstrip('_').lstrip('_')


def get_identity_address(identity_uuid):
    url = "%s/%s/%s/addresses/msisdn" % (settings.IDENTITY_STORE_URL,
                                         "identities", identity_uuid)
    params = {"default": True}
    headers = {
        'Authorization': 'Token %s' % settings.IDENTITY_STORE_TOKEN,
        'Content-Type': 'application/json'
    }
    r = requests.get(url, params=params, headers=headers).json()
    if len(r["results"]) > 0:
        return r["results"][0]["address"]
    else:
        return None


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
