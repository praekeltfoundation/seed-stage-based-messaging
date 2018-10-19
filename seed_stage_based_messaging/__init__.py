__version__ = '0.10.1'
VERSION = __version__


from .celery import app as celery_app

__all__ = ('celery_app',)
