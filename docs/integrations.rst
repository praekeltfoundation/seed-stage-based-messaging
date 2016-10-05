=====================================
Integrations with other Seed services
=====================================

The Seed Stage-based Messaging Store currently integrates with three other
Seed services.

Seed Scheduler
==============

Outgoing integrations
---------------------

.. _new-subscription-integration:

New subscription
~~~~~~~~~~~~~~~~

When a new Subscription object is **created** locally (via the API or the
webhook endpoint) an async Celery task is queued to communicate to the
Seed Scheduler to create a scheduled POST-back to the Stage-based Messaging
Store endpoint (:http:post:`/subscriptions/(int:subscription_id)/send`) on the
given schedule in the subscription.

Updated subscription
~~~~~~~~~~~~~~~~~~~~

When a Subscription object is **updated** locally there are two integrations
to the Seed Scheduler than can occur:

#. If the update is marking the Subscription as complete, an async Celery task
   is queued to communicate to the Seed Scheduler to deactive the scheduled
   POST-backs for this Subscription.

#. If the update is marking the Subscription as inactive, an async Celery task
   is queued to communicate to the Seed Scheduler to deactive the scheduled
   POST-backs for this Subscription.

Incoming integrations
---------------------

Once a schedule has been setup (see :ref:`new-subscription-integration`) in the
Seed Scheduler for a Subscription, the Scheduler will call the
(:http:post:`/subscriptions/(int:subscription_id)/send`) endpoint on the setup
schedule.


Seed Message Sender
===================

Outgoing integrations
---------------------

Message Sending
~~~~~~~~~~~~~~~

When the Subscription send endpoint (
:http:post:`/subscriptions/(int:subscription_id)/send`) is called by the
Scheduler an async Celery task is queued to process the Subscription.

During this process each message that needs to be sent will be queued by
making a request to the Seed Message Sender with the relevant message and
user details.

Project Hub
===========

Incoming integrations
---------------------

New registration
~~~~~~~~~~~~~~~~

When a registration happens on the project hub it calls the
:http:post:`/subscriptions/request` endpoint with the subscription details
to create a new Subscription for the user.
