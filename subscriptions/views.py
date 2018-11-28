from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import (
    DjangoModelPermissions, IsAuthenticated, IsAdminUser
)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django_filters import rest_framework as filters
import django_filters

from .models import BehindSubscription, Subscription, SubscriptionSendFailure
from .serializers import (
    BehindSubscriptionSerializer, SubscriptionSerializer, CreateUserSerializer,
    SubscriptionSendFailureSerializer
)
from .tasks import (
    schedule_disable, scheduled_metrics, requeue_failed_tasks,
    fire_daily_send_estimate, store_resend_request, find_behind_subscriptions
)
from seed_stage_based_messaging.utils import get_available_metrics


class CreatedAtCursorPagination(CursorPagination):
    ordering = "-created_at"


class IdCursorPagination(CursorPagination):
    ordering = "-id"


class SubscriptionFilter(filters.FilterSet):
    created_after = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="lte")
    metadata_has_key = django_filters.CharFilter(field_name='metadata',
                                                 lookup_expr='has_key')
    metadata_not_has_key = django_filters.CharFilter(
        field_name='metadata', lookup_expr='has_key', exclude=True)
    messageset_contains = django_filters.CharFilter(
        field_name='messageset__short_name', lookup_expr='contains')

    class Meta:
        model = Subscription
        exclude = ()
        filter_overrides = {
            JSONField: {
                'filter_class': django_filters.CharFilter,
            }
        }


class SubscriptionViewSet(viewsets.ModelViewSet):

    """ API endpoint that allows Subscription models to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Subscription.objects.all().select_related('messageset')
    serializer_class = SubscriptionSerializer
    filterset_class = SubscriptionFilter
    pagination_class = CreatedAtCursorPagination


class SubscriptionSend(APIView):

    """ Triggers a send for the next subscription message
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        """ Validates subscription data before creating Outbound message
        """
        schedule_disable.delay(kwargs['subscription_id'])
        return Response({'accepted': True}, status=201)


class SubscriptionResend(APIView):

    """ Triggers a re-send for the current subscription message
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        """ Validates subscription data before creating Outbound message
        """
        # Look up subscriber
        subscription_id = kwargs["subscription_id"]
        if Subscription.objects.filter(id=subscription_id).exists():
            status = 202
            accepted = {"accepted": True}
            store_resend_request.apply_async(args=[subscription_id])
        else:
            status = 400
            accepted = {"accepted": False,
                        "reason": "Cannot find subscription with ID {}".format(
                            subscription_id)}
        return Response(accepted, status=status)


class SubscriptionRequest(APIView):

    """ Webhook listener for registrations now needing a subscription
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        """ Validates subscription data before creating Subscription message
        """
        # Ensure that we check for the 'data' key in the request object before
        # attempting to reference it
        if "data" in request.data:
            # This is a workaround for JSONField not liking blank/null refs
            if "metadata" not in request.data["data"]:
                request.data["data"]["metadata"] = {}

            if "initial_sequence_number" not in request.data["data"]:
                request.data["data"]["initial_sequence_number"] = \
                    request.data["data"].get("next_sequence_number")

            subscription = SubscriptionSerializer(data=request.data["data"])
            if subscription.is_valid():
                subscription.save()
                # Return
                status = 201
                accepted = {"accepted": True}
                return Response(accepted, status=status)
            else:
                status = 400
                return Response(subscription.errors, status=status)
        else:
            status = 400
            message = {"data": ["This field is required."]}
            return Response(message, status=status)


class UserView(APIView):
    """ API endpoint that allows users creation and returns their token.
    Only admin users can do this to avoid permissions escalation.
    """
    permission_classes = (IsAdminUser,)

    def post(self, request):
        '''Create a user and token, given an email. If user exists just
        provide the token.'''
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get('email')
        try:
            user = User.objects.get(username=email)
        except User.DoesNotExist:
            user = User.objects.create_user(email, email=email)
        token, created = Token.objects.get_or_create(user=user)

        return Response(
            status=status.HTTP_201_CREATED, data={'token': token.key})


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


class HealthcheckView(APIView):

    """ Healthcheck Interaction
        GET - returns service up - getting auth'd requires DB
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        import seed_stage_based_messaging
        import django
        import rest_framework
        status = 200
        resp = {
            "up": True,
            "result": {
                "database": "Accessible",
                "version": seed_stage_based_messaging.__version__,
                "libraries": {
                    "django": django.__version__,
                    "djangorestframework": rest_framework.__version__
                }
            }
        }
        return Response(resp, status=status)


class FailedTaskViewSet(mixins.ListModelMixin,
                        mixins.RetrieveModelMixin,
                        viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)
    queryset = SubscriptionSendFailure.objects.all()
    serializer_class = SubscriptionSendFailureSerializer
    pagination_class = IdCursorPagination

    def create(self, request):
        status = 201
        resp = {'requeued_failed_tasks': True}
        requeue_failed_tasks.delay()
        return Response(resp, status=status)


class DailyEstimateRun(APIView):

    """ Triggers a daily send estimation
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        task_id = fire_daily_send_estimate.apply_async()
        accepted = {"accepted": True, "task_id": str(task_id)}
        return Response(accepted, status=202)


class DjangoModelViewPermissions(DjangoModelPermissions):
    """
    Django model permissions for viewing
    """
    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
    }


class CanFindBehindSubscriptionsPermission(DjangoModelPermissions):
    """
    Django model permissions for can_find_behind_subscriptions permission
    """
    perms_map = {
        "POST": ["%(app_label)s.can_find_behind_subscriptions"],
    }


class BehindSubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Viewset for querying BehindSubscriptions, and triggering the task that
    creates them.
    """
    queryset = BehindSubscription.objects.select_related(
        "current_messageset", "expected_messageset").all()
    serializer_class = BehindSubscriptionSerializer
    permission_classes = (DjangoModelViewPermissions,)
    pagination_class = CreatedAtCursorPagination

    @action(
        detail=False, methods=["post"],
        permission_classes=(CanFindBehindSubscriptionsPermission,)
    )
    def find_behind_subscriptions(self, request):
        """
        Starts a celery task that looks through active subscriptions to find
        and subscriptions that are behind where they should be, and adds a
        BehindSubscription for them.
        """

        task_id = find_behind_subscriptions.delay()
        return Response(
            {"accepted": True, "task_id": str(task_id)},
            status=status.HTTP_202_ACCEPTED
        )
