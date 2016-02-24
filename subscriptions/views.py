from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.exceptions import ObjectDoesNotExist

from .models import Subscription
from .serializers import SubscriptionSerializer


class SubscriptionViewSet(viewsets.ModelViewSet):

    """ API endpoint that allows Subscription models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    filter_fields = ('identity', 'messageset_id', 'lang', 'active', 'completed',
                     'schedule', 'process_status', 'metadata',)


class SubscriptionSend(APIView):

    """ Triggers a send for the next subscription message
    """
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        """ Validates subscription data before creating Outbound message
        """
        # Look up subscriber
        subscription_id = kwargs["subscription_id"]
        try:
            subscription = Subscription.objects.get(id=subscription_id)
            expect = ["message-id", "send-counter", "schedule-id"]
            if set(expect).issubset(request.data.keys()):
                # Set the next sequence number
                subscription.next_sequence_number = request.data[
                    "send-counter"]
                # Keep the subscription up-to-date for acks later
                subscription.metadata["scheduler_schedule_id"] = \
                    request.data["schedule-id"]
                subscription.metadata["scheduler_message_id"] = \
                    request.data["message-id"]
                subscription.save()
                # TODO: add success signal for listener so message can be
                # created
                # Return
                status = 201
                accepted = {"accepted": True}
            else:
                status = 400
                accepted = {"accepted": False,
                            "reason": "Missing expected body keys"}
        except ObjectDoesNotExist:
            status = 400
            accepted = {"accepted": False,
                        "reason": "Missing subscription in control"}
        return Response(accepted, status=status)


class SubscriptionRequest(APIView):

    """ Webhook listener for registrations now needing a subscription
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        """ Validates subscription data before creating Subscription message
        """
        # This is a workaround for JSONField not liking blank/null refs
        if "metadata" not in request.data["data"]:
            request.data["data"]["metadata"] = {}
        subscription = SubscriptionSerializer(data=request.data["data"])
        if subscription.is_valid(raise_exception=True):
            subscription.save()
            # Return
            status = 201
            accepted = {"accepted": True}
            return Response(accepted, status=status)
