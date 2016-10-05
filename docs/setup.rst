=====
Setup
=====

Installing
==========

The steps required to install the Seed Stage-based Messaging Service are:

#. Get the code from the `Github Project`_ with git:

    .. code-block:: console

        $ git clone https://github.com/praekelt/seed-stage-based-messaging.git

    This will create a directory ``seed-stage-based-messaging`` in your current directory.

.. _Github Project: https://github.com/praekelt/seed-stage-based-messaging

#. Install the Python requirements with pip:

    .. code-block:: console

        $ pip install -r requirements.txt

    This will download and install all the Python packages required to run the
    project.

#. Setup the database:

    .. code-block:: console

        $ python manage migrate

    This will create all the database tables required.

    .. note::
        The PostgreSQL database for the Seed Stage-based Messaging Store needs
        to exist before running this command.
        See :envvar:`STAGE_BASED_MESSAGING_DATABASE` for details.

#. Run the development server:

    .. code-block:: console

        $ python manage.py runserver

    .. note::
        This will run a development HTTP server. This is only suitable for
        testing and development, for production usage please
        see :ref:`running-in-production`

.. _configuration-options:

Configuration Options
=====================

The main configuration file is ``seed_stage_based_messaging/settings.py``.

The following environmental variables can be used to override some default settings:

.. envvar:: SECRET_KEY

    This overrides the Django :django:setting:`SECRET_KEY` setting.

.. envvar:: DEBUG

    This overrides the Django :django:setting:`DEBUG` setting.

.. envvar:: USE_SSL

    Whether to use SSL when build absolute URLs. Defaults to False.

.. envvar:: STAGE_BASED_MESSAGING_DATABASE

    The database parameters to use as a URL in the format specified by the
    `DJ-Database-URL`_ format.

.. _DJ-Database-URL: https://github.com/kennethreitz/dj-database-url

.. envvar:: STAGE_BASED_MESSAGING_SENTRY_DSN

    The DSN to the Sentry instance you would like to log errors to.

.. envvar:: BROKER_URL

    The Broker URL to use with Celery.

.. envvar:: STAGE_BASED_MESSAGING_URL

    The URL of the instance of the Seed Stage-based Messaging API that will be
    used when creating POST-back hooks to this service from other Seed services.

.. envvar:: SCHEDULER_URL

    The URL to the `Seed Scheduler API`_ instance.

.. envvar:: SCHEDULER_API_TOKEN

    The `auth token` to use to connect to the `Seed Scheduler API`_ instance
    above.

.. envvar:: SCHEDULER_INBOUND_API_TOKEN

    The `auth token` to use to connect to this Seed Stage-based Messaging API
    from POST-backs from the `Seed Scheduler API`_ instance.

.. _Seed Scheduler API: https://github.com/praekelt/seed-scheduler

.. envvar:: IDENTITY_STORE_URL

    The URL to the `Seed Identity Store API`_ instance.

.. envvar:: IDENTITY_STORE_TOKEN

    The `auth token` to use to connect to the `Seed Identity Store API`_ instance
    above.

.. _Seed Identity Store API: https://github.com/praekelt/seed-identity-store

.. envvar:: MESSAGE_SENDER_URL

    The URL to the `Seed Message Sender API`_ instance.

.. envvar:: MESSAGE_SENDER_TOKEN

    The `auth token` to use to connect to the `Seed Message Sender API`_ instance
    above.

.. _Seed Message Sender API: https://github.com/praekelt/seed-message-sender

.. envvar:: METRICS_URL

    The URL to the `Go Metrics API`_ instance to push metrics to.

.. envvar:: METRICS_AUTH_TOKEN

    The `auth token` to use to connect to the `Go Metrics API`_ above.

.. _Go Metrics API: https://github.com/praekelt/go-metrics-api