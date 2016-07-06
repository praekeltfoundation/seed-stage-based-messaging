from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.exceptions import ObjectDoesNotExist

from .models import Subscription
from .serializers import SubscriptionSerializer
from .tasks import send_next_message, scheduled_metrics
from seed_stage_based_messaging.utils import get_available_metrics


class SubscriptionViewSet(viewsets.ModelViewSet):

    """ API endpoint that allows Subscription models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    filter_fields = ('identity', 'messageset_id', 'lang', 'active',
                     'completed', 'schedule', 'process_status', 'metadata',)


class SubscriptionSend(APIView):

    """ Triggers a send for the next subscription message
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        """ Validates subscription data before creating Outbound message
        """
        # Look up subscriber
        subscription_id = kwargs["subscription_id"]
        try:
            subscription = Subscription.objects.get(id=subscription_id)
            status = 201
            accepted = {"accepted": True}
            send_next_message.apply_async(args=[str(subscription.id)])
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
        if "metadata" not in request.data["payload"]["data"]:
            request.data["payload"]["data"]["metadata"] = {}
        subscription = SubscriptionSerializer(
            data=request.data["payload"]["data"])
        if subscription.is_valid(raise_exception=True):
            subscription.save()
            # Return
            status = 201
            accepted = {"accepted": True}
            return Response(accepted, status=status)


class MetricsView(APIView):

    """ Metrics Interaction
        GET - returns list of all available metrics on the service
        POST - starts up the task that fires all the scheduled metrics
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        status = 200
        resp = {
            "metrics_available": get_available_metrics()
        }
        return Response(resp, status=status)

    def post(self, request, *args, **kwargs):
        status = 201
        scheduled_metrics.apply_async()
        resp = {"scheduled_metrics_initiated": True}
        return Response(resp, status=status)
