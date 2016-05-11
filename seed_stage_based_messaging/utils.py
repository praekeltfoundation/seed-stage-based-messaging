import requests
from django.conf import settings


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
        return r["results"][0]
    else:
        return None
