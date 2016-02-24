from rest_framework import serializers

from .models import Subscription


class SubscriptionSerializer(serializers.HyperlinkedModelSerializer):
    metadata = serializers.DictField(child=serializers.CharField())

    class Meta:
        model = Subscription
        read_only_fields = ('url', 'id', 'created_at', 'updated_at')
        fields = (
            'url', 'id', 'version', 'identity', 'messageset_id',
            'next_sequence_number', 'lang', 'active', 'completed', 'schedule',
            'process_status', 'metadata', 'created_at', 'updated_at')
