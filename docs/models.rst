===========
Data Models
===========

Content
=======

Schedule
--------

Represents either a fixed date & time or interval based cron-like schedule.

Fields
~~~~~~

**id**

**minute**

**hour**

**day_of_week**

**day_of_month**

**month_of_year**

MessageSet
----------

Represents a group of Messages a recipient can be sent and the default
Schedule they can be sent on.

Fields
~~~~~~

**id**

**short_name**

**notes**

**next_set**

**default_schedule**

**content_type**

**created_at**
    A date and time field of when the record was created.

**updated_at**
    A date and time field of when the record was last updated.



BinaryContent
-------------

Represents binary file storage for use in the Message object.

Fields
~~~~~~

**id**

**content**

**created_at**
    A date and time field of when the record was created.

**updated_at**
    A date and time field of when the record was last updated.



Message
-------

Represents a Message that a recipient can be sent. Can be either text-based or
binary (audio) and is language specific.

Fields
~~~~~~

**id**

**messageset**

**sequence_number**

**lang**

**text_content**

**binary_content**

**created_at**
    A date and time field of when the record was created.

**updated_at**
    A date and time field of when the record was last updated.


Subscriptions
=============

Subscription
------------

Represents a specific Identities subscription to a MessageSet, including the
shedule and current state.

Fields
~~~~~~

**id**

**created_at**
    A date and time field of when the record was created.

**updated_at**
    A date and time field of when the record was last updated.

**created_by**
    A reference to the User account that created this record.

**updated_by**
    A reference to the User account that last updated this record.
