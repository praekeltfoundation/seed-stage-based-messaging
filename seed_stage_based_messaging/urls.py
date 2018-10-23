import os
from django.conf.urls import include, url
from django.contrib import admin
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.documentation import include_docs_urls
from subscriptions import views

admin.site.site_header = os.environ.get('SUBSCRIPTIONS_TITLE',
                                        'Seed Stage Based Messaging Admin')


urlpatterns = [
    path('admin/', admin.site.urls),
    url(r'^api/auth/',
        include('rest_framework.urls', namespace='rest_framework')),
    url(r'^api/token-auth/', obtain_auth_token),
    url(r'^api/metrics/', views.MetricsView.as_view()),
    url(r'^api/health/', views.HealthcheckView.as_view()),
    url(r'^', include('subscriptions.urls')),
    url(r'^', include('contentstore.urls')),
    url(r'^docs/', include_docs_urls(title="Seed Stage Based Messaging")),
]
