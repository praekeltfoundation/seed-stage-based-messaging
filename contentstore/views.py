from .models import Schedule, MessageSet, Message, BinaryContent
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from .serializers import (ScheduleSerializer, MessageSetSerializer,
                          MessageSerializer, BinaryContentSerializer,
                          MessageListSerializer, MessageSetMessagesSerializer)


class ScheduleViewSet(ModelViewSet):

    """
    API endpoint that allows Schedule models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer


class MessageSetViewSet(ModelViewSet):

    """
    API endpoint that allows MessageSet models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = MessageSet.objects.all()
    serializer_class = MessageSetSerializer
    filter_fields = ('short_name', 'content_type', )


class MessageViewSet(ModelViewSet):

    """
    API endpoint that allows Message models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    filter_fields = ('messageset', 'sequence_number', 'lang', )


class BinaryContentViewSet(ModelViewSet):

    """
    API endpoint that allows BinaryContent models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = BinaryContent.objects.all()
    serializer_class = BinaryContentSerializer


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
