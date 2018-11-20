from .models import Schedule, MessageSet, Message, BinaryContent

from rest_framework import serializers


class ScheduleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Schedule
        fields = ('id', 'minute', 'hour', 'day_of_week', 'day_of_month',
                  'month_of_year')


class MessageSetSerializer(serializers.ModelSerializer):

    class Meta:
        model = MessageSet
        fields = ('id', 'short_name', 'label', 'content_type', 'notes',
                  'next_set', 'default_schedule', 'created_at', 'updated_at')


class BinaryContentSerializer(serializers.ModelSerializer):

    class Meta:
        model = BinaryContent
        fields = ('id', 'content')


class MessageSerializer(serializers.ModelSerializer):

    class Meta:
        model = Message
        fields = ('id', 'messageset', 'sequence_number', 'lang',
                  'text_content', 'binary_content', 'created_at', 'updated_at')


class MessageListSerializer(serializers.ModelSerializer):

    """
        Only used for get views, because binary relational serializer is not
        something that works nicely with posts
    """
    binary_content = BinaryContentSerializer(many=False, read_only=True)

    class Meta:
        model = Message
        fields = ('id', 'messageset', 'sequence_number', 'lang',
                  'text_content', 'binary_content', 'created_at', 'updated_at')


class MessageSetMessagesSerializer(serializers.ModelSerializer):
    messages = MessageListSerializer(many=True, read_only=True)

    class Meta:
        model = MessageSet
        fields = ('id', 'short_name', 'notes', 'next_set', 'default_schedule',
                  'messages', 'created_at', 'updated_at')
