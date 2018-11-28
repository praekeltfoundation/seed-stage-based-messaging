from django.conf.urls import url, include
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register(r'subscriptions', views.SubscriptionViewSet)
router.register(r'failed-tasks', views.FailedTaskViewSet)
router.register(r'behind-subscriptions', views.BehindSubscriptionViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browseable API.
urlpatterns = [
    url(r'^api/v1/', include(router.urls)),
    url(r'^api/v1/subscriptions/(?P<subscription_id>.+)/send$',
        views.SubscriptionSend.as_view(), name='subscription-send'),
    url(r'^api/v1/subscriptions/(?P<subscription_id>.+)/resend$',
        views.SubscriptionResend.as_view()),
    url(r'^api/v1/subscriptions/request$',
        views.SubscriptionRequest.as_view()),
    url(r'^api/v1/user/token/$', views.UserView.as_view(),
        name='create-user-token'),
    url(r'^api/v1/runsendestimate$',
        views.DailyEstimateRun.as_view()),
]
