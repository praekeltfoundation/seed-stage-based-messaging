from django.apps import AppConfig


class ContentStoreAppConfig(AppConfig):
    name = 'contentstore'

    def ready(self):
        import contentstore.signals
        contentstore.signals
