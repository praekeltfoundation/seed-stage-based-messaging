FROM praekeltfoundation/django-bootstrap
ENV DJANGO_SETTINGS_MODULE "seed_stage_based_messaging.settings"
RUN ./manage.py collectstatic --noinput
ENV APP_MODULE "seed_stage_based_messaging.wsgi:application"
