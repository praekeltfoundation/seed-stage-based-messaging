FROM praekeltfoundation/django-bootstrap
ENV DJANGO_SETTINGS_MODULE "seed_stage_based_messaging.settings"
RUN django-admin collectstatic --noinput
CMD ["seed_stage_based_messaging.wsgi:application"]
