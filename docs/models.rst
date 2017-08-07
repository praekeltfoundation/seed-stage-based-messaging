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
    An auto incrementing integer unique identifier for the record.

**minute**
    A character field representing the minute portion of the schedule.
    Defaults to ``*`` but can be a comma separated list of numbers between 0
    and 59.

**hour**
    A character field representing the hour portion of the schedule.
    Defaults to ``*`` but can be a comma separated list of numbers between 0
    and 23.

**day_of_week**
    A character field representing the day of the week portion of the schedule.
    Defaults to ``*`` but can be a comma separated list of numbers between 1
    and 7 where 1 = Monday and 7 = Sunday.

**day_of_month**
    A character field representing the day of the month portion of the
    schedule. Defaults to ``*`` but can be a comma separated list of numbers
    between 1 and 31.

**month_of_year**
    A character field representing the month of the year portion of the
    schedule. Defaults to ``*`` but can be a comma separated list of numbers
    between 1 and 12.

MessageSet
----------

Represents a group of Messages a recipient can be sent and the default
Schedule they can be sent on.

Fields
~~~~~~

**id**
    An auto incrementing integer unique identifier for the record.

**short_name**
    A unique name that identifies this MessageSet.

**notes**
    An optional free text field for notes about this MessageSet.

**next_set**
    An optional self-referencing link to a MessageSet that should follow from
    this one.

**default_schedule**
    A reference to a Schedule used as the default for this MessageSet.

**content_type**
    A choice field between `audio` and `text` representing the type of content
    this MessageSet contains.

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
    An auto incrementing integer unique identifier for the record.

**content**
    A FileField that represents the binary content's location on disk.

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
    An auto incrementing integer unique identifier for the record.

**messageset**
    A reference to the MessageSet this message belongs to.

**sequence_number**
    A required integer representing the order of this message in the set.

**lang**
    An ISO639-3 language code.

**text_content**
    Optional text content for the message.

**binary_content**
    Optional reference to a BinaryContent.

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
    A UUID 4 unique identifier for the record.

**identity**
    A UUID reference to an Identity stored in the Seed Identity Store.

**version**
    An integer version number of the Subscription schema used.

**messageset**
    A reference to the MessageSet for this Subscription.

**next_sequence_number**
    The integer Message sequence number to use for this Subscription.

**lang**
    An ISO639-3 language code representing the preferred language for this
    Subscription.

**active**
    A boolean of the active status.

**completed**
    A boolean of the complete status.

**schedule**
    A reference to the Schedule to use for this Subscription.

**process_status**
    A integer flag representing the process status of this subscription.

    | -2 = error
    | -1 = error
    | 0 = ready
    | 1 = in process
    | 2 = completed

**metadata**
    A JSON field of `metadata` to be stored with the Subscription.

**created_at**
    A date and time field of when the record was created.

**updated_at**
    A date and time field of when the record was last updated.

**created_by**
    A reference to the User account that created this record.

**updated_by**
    A reference to the User account that last updated this record.
