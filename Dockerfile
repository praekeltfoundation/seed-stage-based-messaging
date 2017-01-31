FROM praekeltfoundation/django-bootstrap:onbuild
ENV DJANGO_SETTINGS_MODULE "seed_stage_based_messaging.settings"
RUN python manage.py collectstatic --noinput
ENV APP_MODULE "seed_stage_based_messaging.wsgi:application"
