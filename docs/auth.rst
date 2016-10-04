================================
Authentication and Authorization
================================

Basics
======

Authentication to the Seed Stage-Based Messaging Store API is provided the
`Token Authentication`_ feature of the `Django REST Framework`_.

.. _Django REST Framework: http://www.django-rest-framework.org/api-guide/authentication/#tokenauthentication
.. _Token Authentication: http://www.django-rest-framework.org/api-guide/authentication/#tokenauthentication

In short, each user of this API needs have been supplied a unique secret token
that must be provided in the ``Authorization`` HTTP header of every request made
to this API.

An example request with the ``Authorization`` header might look like this:

.. sourcecode:: http

    POST /endpoint/ HTTP/1.1
    Host: <stage-based-messaging-store-domain>
    Content-Type: application/json
    Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b


Users and Groups
================

`User` and `Group` objects are provided by the Django Auth framework and can
be added and created through the normal maintenance methods (Django Admin,
Dgango Shell, ...).

There is also a rudimentary API endpoint: :http:post:`/user/token/` that will
create a user and token for a given email address (or just a token if a user
with that email address already exists).


Authorization and permissions
=============================

All of the current API endpoints do not require any specific permissions other
than a valid authenticated user.

The only exception to this is :http:post:`/user/token/` which requires an
admin level user.
