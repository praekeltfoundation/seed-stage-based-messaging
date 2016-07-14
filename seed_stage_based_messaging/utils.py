import requests
from django.conf import settings
from contentstore.models import MessageSet


def get_identity(identity_uuid):
    url = "%s/%s/%s/" % (settings.IDENTITY_STORE_URL, "identities",
                         identity_uuid)
    headers = {
        'Authorization': 'Token %s' % settings.IDENTITY_STORE_TOKEN,
        'Content-Type': 'application/json'
    }
    r = requests.get(url, headers=headers)
    return r.json()


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
        available_metrics.append(
            "subscriptions.%s.active.last" % messageset.short_name)

    return available_metrics
