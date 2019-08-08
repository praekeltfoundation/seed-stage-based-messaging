==========================
Seed Stage-Based Messaging
==========================

The Seed Stage-Based Messaging Store is one of the microservices in the Seed
Stack.

The Stage-Based Messaging Store has the following key responsibilities:

- Store the stage-based content (both audio and text).
- Store the stage-based content schedules.
- Store the stage-based content subscriptions for each user.

This uses the django cache framework to provide locking for the processing of
subscriptions, so please ensure that the `REDIS_URL` setting is set.
