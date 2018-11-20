from .models import Schedule, MessageSet, Message, BinaryContent
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import (ScheduleSerializer, MessageSetSerializer,
                          MessageSerializer, BinaryContentSerializer,
                          MessageListSerializer, MessageSetMessagesSerializer)
from .tasks import sync_audio_messages, queue_subscription_send


class IdCursorPagination(CursorPagination):
    ordering = "id"


class ScheduleViewSet(ModelViewSet):

    """
    API endpoint that allows Schedule models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    pagination_class = IdCursorPagination

    @action(methods=['post'], detail=True)
    def send(self, request, pk=None):
        """
        Sends all the subscriptions for the specified schedule
        """
        schedule = self.get_object()
        queue_subscription_send.delay(str(schedule.id))

        return Response({}, status=status.HTTP_202_ACCEPTED)


class MessageSetViewSet(ModelViewSet):

    """
    API endpoint that allows MessageSet models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = MessageSet.objects.all()
    serializer_class = MessageSetSerializer
    filterset_fields = ('short_name', 'content_type', )
    pagination_class = IdCursorPagination


class MessageViewSet(ModelViewSet):

    """
    API endpoint that allows Message models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    filterset_fields = ('messageset', 'sequence_number', 'lang', )
    pagination_class = IdCursorPagination


class BinaryContentViewSet(ModelViewSet):

    """
    API endpoint that allows BinaryContent models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = BinaryContent.objects.all()
    serializer_class = BinaryContentSerializer
    pagination_class = IdCursorPagination


class MessagesContentView(ModelViewSet):

    """
    A simple ViewSet for viewing more detailed message content.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Message.objects.all()
    serializer_class = MessageListSerializer


class MessagesetMessagesContentView(ModelViewSet):

    """
    API endpoint that allows MessageSet models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = MessageSet.objects.all()
    serializer_class = MessageSetMessagesSerializer


class MessagesetLanguageView(APIView):

    """
    GET - returns languages per message set
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        status = 200
        data = {}
        for messageset in MessageSet.objects.all():
            data[messageset.id] = messageset.messages.order_by(
                'lang').values_list('lang', flat=True).distinct()

        return Response(data, status=status)


class SyncAudioFilesView(APIView):

    """ SyncAudioFiles Interaction
        POST - starts up the task that sync the audio files with a sftp folder.
    """
    def post(self, request, *args, **kwargs):
        status = 202

        task_id = sync_audio_messages.apply_async()

        resp = {
            "sync_audio_files_initiated": True,
            "task_id": str(task_id),
        }

        return Response(resp, status=status)
