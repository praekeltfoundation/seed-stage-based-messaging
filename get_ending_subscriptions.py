import csv
from os import environ
from datetime import datetime, timedelta
from requests import ConnectionError
from contentstore.models import MessageSet
from subscriptions.models import Subscription

from seed_services_client import IdentityStoreApiClient, HubApiClient


def get_ending_subs(messageset_name, hub_url, hub_token,
                    start_date=None, end_date=None,
                    identity_store_url=environ.get('IDENTITY_STORE_URL'),
                    identity_store_token=environ.get('IDENTITY_STORE_TOKEN')):
    #
    if start_date:
        start_date = datetime.strptime(start_date, '%Y%m%d')
    else:
        start_date = datetime.now()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y%m%d') + timedelta(days=1)
    else:
        end_date = datetime.now() + timedelta(days=1)
    #
    messageset = MessageSet.objects.get(short_name=messageset_name)
    set_max = messageset.messages.filter(lang="eng_ZA").count()
    schedule = messageset.default_schedule
    #
    # Number of times the schedule will run before the start of the timeframe
    runs_before_start = len(
        schedule.get_run_times_between(datetime.now(), start_date))
    # Number of times the schedule will run before the end of the timeframe
    runs_before_end = len(
        schedule.get_run_times_between(datetime.now(), end_date))
    #
    # Any schedules older than this will expire before the window
    max_next_msg = set_max - runs_before_start
    # Any schedules newer than this will expire after the window
    min_next_msg = set_max - runs_before_end
    #
    subscriptions = Subscription.objects.filter(
        messageset=messageset, active=True, completed=False,
        next_sequence_number__gt=min_next_msg,
        next_sequence_number__lte=max_next_msg)
    #
    identity_client = IdentityStoreApiClient(
        identity_store_token, identity_store_url)
    hub_client = HubApiClient(hub_token, hub_url)
    #
    compile_temp_csv(subscriptions, hub_client, identity_client)


def compile_temp_csv(subscriptions, hub_client, identity_client):
    print("Retrieving and writing data to terminating_subscriptions.csv")
    with open("terminating_subscriptions.csv", 'w+b') as csvfile:
        fieldnames = [
            'Subscription', 'MSISDN', 'Facility code', 'EDD', 'ID Number',
            'Language']
        csvwriter = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                   restval="Unavailable")
        csvwriter.writeheader()
        for sub in subscriptions.iterator():
            row_data = {'Subscription': sub.id}
            print("Retrieving registration data for %s" % sub.id)
            registrations = hub_client.get_registrations(
                {'registrant_id': sub.identity})
            if registrations['count']:
                try:
                    row_data.update(
                        get_registration_data(registrations['results'][0]))
                except ConnectionError:
                    print("Error retrieving registration data.")
            if "MSISDN" not in row_data or "EDD" not in row_data or "Language"\
                    not in row_data:
                print("Some registration data missing. Retrieving identity "
                      "data for %s" % sub.id)
                try:
                    identity = identity_client.get_identity(sub.identity)
                    if identity:
                        row_data.update(get_identity_data(identity))
                except ConnectionError:
                    print("Error retrieving identity data.")
            csvwriter.writerow(row_data)
        csvfile.seek(0)


def get_registration_data(registration):
    data = {}
    if "faccode" in registration['data']:
        data['Facility code'] = registration['data']['faccode']
    if "msisdn_registrant" in registration['data']:
        data['MSISDN'] = \
            registration['data']['msisdn_registrant']
    if "edd" in registration['data']:
        data['EDD'] = registration['data']['edd']
    if "language" in registration['data']:
        data['Language'] = registration['data']['language']
    if "sa_id_no" in registration['data']:
        data['ID Number'] = registration['data']['sa_id_no']
    return data


def get_identity_data(identity):
    data = {}
    msisdn = \
        identity['details']['addresses']['msisdn'].keys()[0]
    data['MSISDN'] = msisdn
    if "lang_code" in identity['details']:
        data['Language'] = identity['details']['lang_code']
    if "last_edd" in identity['details']:
        data['EDD'] = identity['details']['last_edd']
    return data
