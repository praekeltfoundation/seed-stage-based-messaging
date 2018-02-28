from celery.task import Task
from django.conf import settings
from sftpclone import sftpclone


class SyncAudioMessages(Task):

    def run(self, **kwargs):
        if settings.AUDIO_FTP_HOST:
            src = '{}/{}/'.format(settings.BASE_DIR, settings.MEDIA_ROOT)

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
