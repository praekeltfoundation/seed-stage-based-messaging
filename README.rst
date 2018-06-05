==========================
Seed Stage-Based Messaging
==========================

The Seed Stage-Based Messaging Store is one of the microservices in the Seed
Stack.

The Stage-Based Messaging Store has the following key responsibilities:

- Store the stage-based content (both audio and text).
- Store the stage-based content schedules.
- Store the stage-based content subscriptions for each user.


Changelog
---------

0.10.0
______
 - Changed to having a schedule per schedule, instead of a schedule per 
   subscription. Any new or updated schedules will automatically be created or
   updated in the scheduler, but for existing schedules, there's a
   `sync_schedules` management command. Existing schedules linking directly
   to subscriptions will be cancelled whenever they get called.
 - Added a new celery queue, 'highmemory', which has the task to queue up all
   the subscription sends for each schedule when the endpoint is called
