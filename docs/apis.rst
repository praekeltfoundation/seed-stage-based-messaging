===========
API Details
===========

The Seed Stage-Based Messaging Store provides REST like API with JSON payloads.

The root URL for all of the endpoints is:

    :samp:`https://{<stage-based-messaging-store-domain>}/api/`


Authenticating to the API
=========================

Please see the :doc:`Authentication and Authorization <auth>` document.

Pagination
==========

When the results set is larger than a configured amount, the data is broken up
into pages using the limit and offset parameters.

Paginated endpoints will provide information about the total amount of items
available along with links to the previous and next pages (where available) in
the returned JSON data.

.. http:get:: /(any)/
    :noindex:

    :query limit: the amount of record to limit a page of results to.
    :query offset: the starting position of the query in relation to the complete set of unpaginated items
    :>json int count: the total number of results available
    :>json string previous: the URL to the previous page of results (if available)
    :>json string next: the URL to the next page of results (if available)

    **Example request**:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
            "count": 50,
            "next": "http://sbm.example.org/api/v1/enpoint/?limit=10&offset=30",
            "previous": "http://smb.example.org/api/v1/endpoint/?limit=10&offset=10",
            "results": []
        }


Endpoints
=========

The endpoints provided by the Seed Stage-Based Messaging Store are split into
two categories, core endpoints and helper endpoints

Core
----

The root URL for all of the core endpoints includes the version prefix
(:samp:`https://{<stage-based-messaging-store-domain>}/api/v1/`)

Content
~~~~~~~

.. http:post:: /user/token/

    Creates a user and token for the given email address.

    If a user already exists for the given email address, the existing user
    account is used to generate a new token.

    :<json string email: the email address of the user to create or use.
    :>json string token: the auth token generated for the given user.
    :status 201: token successfully created.
    :status 400: an email address was not provided or was invalid.
    :status 401: the token is invalid/missing.


    **Example request**:

    .. sourcecode:: http

        POST /user/token/ HTTP/1.1
        Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b

        {
            "email": "bob@example.org"
        }


    **Example response**:

    .. sourcecode:: http

        HTTP/1.1 201 Created
        Content-Type: application/json

        {
            "token": "c05fbab6d5f912429052830c77eeb022249324cb"
        }


.. http:get:: /schedule/

.. http:post:: /schedule/

.. http:get:: /schedule/(int:schedule_id)/

.. http:put:: /schedule/(int:schedule_id)/

.. http:delete:: /schedule/(int:schedule_id)/


.. http:get:: /messageset/

.. http:post:: /messageset/

.. http:get:: /messageset/(int:messageset_id)/

.. http:put:: /messageset/(int:messageset_id)/

.. http:delete:: /messageset/(int:messageset_id)/

.. http:get:: /messageset/(int:messageset_id)/messages/


.. http:get:: /message/

.. http:post:: /message/

.. http:get:: /message/(int:message_id)/

.. http:put:: /message/(int:message_id)/

.. http:delete:: /message/(int:message_id)/

.. http:get:: /message/(int:message_id)/content/


.. http:get:: /binarycontent/

.. http:post:: /binarycontent/

.. http:get:: /binarycontent/(int:binarycontent_id)/

.. http:put:: /binarycontent/(int:binarycontent_id)/

.. http:delete:: /binarycontent/(int:binarycontent_id)/

Subscriptions
~~~~~~~~~~~~~

.. http:get:: /subscriptions/

.. http:post:: /subscriptions/

.. http:get:: /subscriptions/(int:subscriptions_id)/

.. http:put:: /subscriptions/(int:subscriptions_id)/

.. http:delete:: /subscriptions/(int:subscriptions_id)/

.. http:get:: /subscriptions/(int:subscriptions_id)/send/

.. http:get:: /subscriptions/(int:subscriptions_id)/request/

Helpers
-------

The root URL for the helper endpoints does not include a version prefix
(:samp:`https://{<stage-based-messaging-store-domain>}/api/`)

.. http:get:: /metrics/
    :noindex:

    Returns a list of all the available metric keys provided by this service.

    :status 200: no error
    :status 401: the token is invalid/missing.

.. http:post:: /metrics/
    :noindex:

    Starts a task that fires all scheduled metrics.

    :status 200: no error
    :status 401: the token is invalid/missing.

.. http:get:: /health/
    :noindex:

    Returns a basic health check status.

    :status 200: no error
    :status 401: the token is invalid/missing.
