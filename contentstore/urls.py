from django.conf.urls import url, include
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register(r'schedule', views.ScheduleViewSet)
router.register(r'messageset', views.MessageSetViewSet)
router.register(r'message', views.MessageViewSet)
router.register(r'binarycontent', views.BinaryContentViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browseable API.
urlpatterns = [
    url(r'^api/v1/', include(router.urls)),
    url(r'^api/v1/message/(?P<pk>.+)/content$',
        views.MessagesContentView.as_view({'get': 'retrieve'})),
    url(r'^api/v1/messageset/(?P<pk>.+)/messages$',
        views.MessagesetMessagesContentView.as_view({'get': 'retrieve'})),
    url(r'^api/v1/messageset_languages/$',
        views.MessagesetLanguageView.as_view()),
    url(r'^api/v1/sync_audio_files/$',
        views.SyncAudioFilesView.as_view()),
]
