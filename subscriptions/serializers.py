from rest_framework import serializers

from .models import Subscription, SubscriptionSendFailure


class CreateUserSerializer(serializers.Serializer):
    email = serializers.EmailField()


class SubscriptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Subscription
        read_only_fields = ('url', 'id', 'created_at', 'updated_at')
        fields = (
            'url', 'id', 'version', 'identity', 'messageset',
            'next_sequence_number', 'lang', 'active', 'completed', 'schedule',
            'process_status', 'metadata', 'created_at', 'updated_at',
            'initial_sequence_number')


class SubscriptionSendFailureSerializer(
        serializers.HyperlinkedModelSerializer):
    subscription_id = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = SubscriptionSendFailure
        fields = ('url', 'id', 'subscription', 'subscription_id', 'task_id',
                  'initiated_at', 'reason')
