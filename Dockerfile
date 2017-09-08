# This is a development Dockerfile. For versioned Dockerfiles see:
# https://github.com/praekeltfoundation/docker-seed
FROM praekeltfoundation/django-bootstrap:py2

COPY . /app
RUN pip install -e .

ENV DJANGO_SETTINGS_MODULE "seed_stage_based_messaging.settings"
RUN python manage.py collectstatic --noinput
CMD ["seed_stage_based_messaging.wsgi:application"]
