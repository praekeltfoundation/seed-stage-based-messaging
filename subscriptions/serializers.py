from rest_framework import serializers

from .models import BehindSubscription, Subscription, SubscriptionSendFailure


class CreateUserSerializer(serializers.Serializer):
    email = serializers.EmailField()


class SubscriptionSerializer(serializers.ModelSerializer):
    messageset_label = serializers.SlugRelatedField(
        source='messageset', slug_field='label', read_only=True)

    class Meta:
        model = Subscription
        read_only_fields = ('url', 'id', 'created_at', 'updated_at')
        fields = (
            'url', 'id', 'version', 'identity', 'messageset',
            'next_sequence_number', 'lang', 'active', 'completed', 'schedule',
            'process_status', 'metadata', 'created_at', 'updated_at',
            'initial_sequence_number', 'messageset_label')


class SubscriptionSendFailureSerializer(
        serializers.HyperlinkedModelSerializer):
    subscription_id = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = SubscriptionSendFailure
        fields = ('url', 'id', 'subscription', 'subscription_id', 'task_id',
                  'initiated_at', 'reason')


class BehindSubscriptionSerializer(serializers.HyperlinkedModelSerializer):
    subscription_id = serializers.PrimaryKeyRelatedField(read_only=True)
    current_messageset_id = serializers.PrimaryKeyRelatedField(read_only=True)
    current_messageset_name = serializers.StringRelatedField(
        source="current_messageset")
    expected_messageset_id = serializers.PrimaryKeyRelatedField(read_only=True)
    expected_messageset_name = serializers.StringRelatedField(
        source="expected_messageset")

    class Meta:
        model = BehindSubscription
        fields = (
            "id", "subscription", "subscription_id", "messages_behind",
            "current_messageset", "current_messageset_id",
            "current_messageset_name", "current_sequence_number",
            "expected_messageset", "expected_messageset_id",
            "expected_messageset_name", "expected_sequence_number",
            "created_at"
        )
