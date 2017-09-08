=================================
Production requirements and setup
=================================

.. _running-in-production:

Running in Production
=====================

The Seed Stage-Based Messaging Store is expected to be run in a Docker
container and as such a Docker file is provided in the source code repository.

The web service portion and celery work portion of the Stage-Based Messaging
Store are expected to be run in different instances of the same Docker container.

An example production setup might look like this:

.. image:: _images/stage-based-messaging-store-production.png
