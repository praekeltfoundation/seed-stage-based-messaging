from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.exceptions import ObjectDoesNotExist

from .models import Subscription
from .serializers import SubscriptionSerializer
from .tasks import create_message


class SubscriptionViewSet(viewsets.ModelViewSet):

    """ API endpoint that allows Subscription models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    filter_fields = ('contact', 'messageset_id', 'lang', 'active', 'completed',
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
                # Create and populate the message which will trigger send task
                create_message.apply_async(args=[
                    str(subscription.contact.id),
                    subscription.messageset_id,
                    subscription.next_sequence_number,
                    subscription.lang,
                    str(subscription.id)])
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
