
"""
Client for Messaging Content Store HTTP services APIs.

"""
import requests
import json


class SchedulerApiClient(object):

    """
    Client for Scheduler API.

    :param str api_token:

        An API Token.

    :param str api_url:
        The full URL of the API. Defaults to
        ``http://testserver/hello-mama/api/v1``.

    """

    def __init__(self, api_token, api_url=None, session=None):
        if api_url is None:
            api_url = "http://testserver/hello-mama/api/v1"
        self.api_url = api_url
        self.headers = {
            'Content-Type': 'application/json',
            'Authorisation': api_token
        }
        if session is None:
            session = requests.Session()
        session.headers.update(self.headers)
        self.session = session

    def call(self, endpoint, method, obj=None, params=None, data=None):
        if obj is None:
            url = '%s/%s' % (self.api_url.rstrip('/'), endpoint)
        else:
            url = '%s/%s/%s' % (self.api_url.rstrip('/'), endpoint, obj)
        result = {
            'get': self.session.get,
            'post': self.session.post,
            'put': self.session.post,
            'delete': self.session.delete,
        }.get(method, None)(url, params=params, data=json.dumps(data))
        result.raise_for_status()
        if method is "delete":  # DELETE returns blank body
            return {"success": True}
        else:
            return result.json()

    def get_schedules(self, params=None):
        return self.call('schedules', 'get', params=params)

    def get_schedule(self, schedule_id):
        return self.call('schedules', 'get', obj=schedule_id)

    def get_schedule_messages(self, schedule_id):
        return self.call('schedules', 'get',
                         obj='%s/messages' % schedule_id)

    def create_schedule(self, schedule):
        return self.call('schedules', 'post', data=schedule)

    def update_schedule(self, schedule_id, schedule):
        return self.call('schedules', 'put', obj=schedule_id,
                         data=schedule)

    def delete_schedule(self, schedule_id):
        # Schedule messages must all be deleted first for FK reasons
        return self.call('schedules', 'delete', obj=schedule_id)

    def get_messages(self, params=None):
        return self.call('messages', 'get', params=params)

    def get_message(self, message_id):
        return self.call('messages', 'get', obj=message_id)

    def create_message(self, message):
        return self.call('messages', 'post', data=message)

    def update_message(self, message_id, message):
        return self.call('messages', 'put', obj=message_id,
                         data=message)

    def delete_message(self, message_id):
        return self.call('messages', 'delete', obj=message_id)
