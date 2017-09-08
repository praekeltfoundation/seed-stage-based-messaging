from django.core.management.base import BaseCommand
from django.core.validators import URLValidator
from django.conf import settings
from requests import exceptions
from demands import HTTPServiceError

from subscriptions.models import Subscription

from seed_services_client import HubApiClient, IdentityStoreApiClient


def url_validator(url_str):
    URLValidator(url_str)
    return url_str


class Command(BaseCommand):
    help = ("Searches all subscription with status 5 and updates the linked "
            "identity and registration object. This is for excluding the "
            "relevant items from reports")

    def add_arguments(self, parser):
        parser.add_argument(
            '--hub-url',
            type=url_validator,
            help='The HUB url to use'
        )
        parser.add_argument(
            '--hub-token',
            type=str,
            help=('The HUB API token')
        )
        parser.add_argument(
            '--identity-url',
            type=url_validator,
            default=settings.IDENTITY_STORE_URL,
            help='The Identity Store url to use'
        )
        parser.add_argument(
            '--identity-token',
            type=str,
            default=settings.IDENTITY_STORE_TOKEN,
            help=('The Identity Store API token')
        )
        parser.add_argument(
            '--hub-identity-field',
            type=str,
            default='mother_id',
            help=('The HUB Identity field')
        )

    def handle(self, *args, **options):
        hub_url = options['hub_url']
        hub_token = options['hub_token']
        id_url = options['identity_url']
        id_token = options['identity_token']
        hub_id_field = options['hub_identity_field']

        if not hub_url or not hub_token:
            self.warning("hub-url and hub-token is required.")
            return

        hubApi = HubApiClient(hub_token, hub_url)
        idApi = IdentityStoreApiClient(id_token, id_url)

        subscriptions = Subscription.objects.filter(process_status=5)

        reg_count = 0
        id_count = 0
        for subscription in subscriptions.iterator():
            identity = subscription.identity

            # find and update linked registrations
            registrations = hubApi.get_registrations({hub_id_field: identity})

            for registration in registrations['results']:

                if not registration['data'].get('exclude_report', False):
                    registration['data']['exclude_report'] = True

                    try:
                        hubApi.update_registration(
                            registration['id'], {'data': registration['data']})
                        reg_count += 1
                    except exceptions.ConnectionError as exc:
                        self.warning(
                            'Connection error to Hub API: {}'.format(exc))
                    except HTTPServiceError as exc:
                        self.warning('Invalid Hub API response({}): {}'.format(
                            exc.response.status_code, exc.response.url))

            # find and update linked identities
            identity = idApi.get_identity(identity)

            if not identity['details'].get('exclude_report', False):
                identity['details']['exclude_report'] = True

                try:
                    idApi.update_identity(identity['id'],
                                          {'details': identity['details']})
                    id_count += 1
                except exceptions.ConnectionError as exc:
                    self.warning(
                        'Connection error to Identity API: {}'.format(exc))
                except HTTPServiceError as exc:
                    self.warning(
                        'Invalid Identity Store API response({}): {}'.format(
                            exc.response.status_code, exc.response.url))

        self.success('Updated %s identities and %s registrations.' % (
            id_count, reg_count))

    def log(self, level, msg):
        self.stdout.write(level(msg))

    def warning(self, msg):
        self.log(self.style.WARNING, msg)

    def success(self, msg):
        self.log(self.style.SUCCESS, msg)
