import os
import requests

from celery.task import Task
from django.conf import settings
from sftpclone import sftpclone

from .models import BinaryContent
from subscriptions.tasks import make_absolute_url


class SyncAudioMessages(Task):

    def run(self, **kwargs):
        if settings.AUDIO_FTP_HOST:

            src = '{}/{}/'.format(settings.BASE_DIR, settings.MEDIA_ROOT)

            existing_files = os.listdir(src)

            files = BinaryContent.objects.all()
            for item in files.iterator():

                if item.content.name not in existing_files:
                    r = requests.get(make_absolute_url(item.content.url))

                    local_path = '{}{}'.format(src, item.content.name)
                    with open(local_path, "w") as f:
                        f.write(r.content)

            root = settings.AUDIO_FTP_ROOT
            host = settings.AUDIO_FTP_HOST
            username = settings.AUDIO_FTP_USER
            password = settings.AUDIO_FTP_PASS
            port = int(settings.AUDIO_FTP_PORT)

            cloner = sftpclone.SFTPClone(
                src,
                "{}:{}@{}:{}".format(username, password, host, root),
                port=port,
                delete=False
            )
            cloner.run()


sync_audio_messages = SyncAudioMessages()
