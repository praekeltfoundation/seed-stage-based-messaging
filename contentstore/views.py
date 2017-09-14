from .models import Schedule, MessageSet, Message, BinaryContent
from rest_framework.viewsets import ModelViewSet
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import (ScheduleSerializer, MessageSetSerializer,
                          MessageSerializer, BinaryContentSerializer,
                          MessageListSerializer, MessageSetMessagesSerializer)


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


class MessageSetViewSet(ModelViewSet):

    """
    API endpoint that allows MessageSet models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = MessageSet.objects.all()
    serializer_class = MessageSetSerializer
    filter_fields = ('short_name', 'content_type', )
    pagination_class = IdCursorPagination


class MessageViewSet(ModelViewSet):

    """
    API endpoint that allows Message models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    filter_fields = ('messageset', 'sequence_number', 'lang', )
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
