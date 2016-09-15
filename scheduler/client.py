
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
        ``http://seed-scheduler/api/v1``.

    """

    def __init__(self, api_token, api_url=None, session=None):
        if api_url is None:
            api_url = "http://seed-scheduler/api/v1"
        self.api_url = api_url
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Token %s' % api_token
        }
        if session is None:
            session = requests.Session()
        session.headers.update(self.headers)
        self.session = session

    def call(self, endpoint, method, obj=None, params=None, data=None):
        if obj is None:
            url = '%s/%s/' % (self.api_url.rstrip('/'), endpoint)
        else:
            url = '%s/%s/%s/' % (self.api_url.rstrip('/'), endpoint, obj)
        result = {
            'get': self.session.get,
            'post': self.session.post,
            'patch': self.session.patch,
            'delete': self.session.delete,
        }.get(method, None)(url, params=params, data=json.dumps(data))
        result.raise_for_status()
        if method is "delete":  # DELETE returns blank body
            return {"success": True}
        else:
            return result.json()

    def get_schedules(self, params=None):
        return self.call('schedule', 'get', params=params)

    def get_schedule(self, schedule_id):
        return self.call('schedule', 'get', obj=schedule_id)

    def create_schedule(self, schedule):
        return self.call('schedule', 'post', data=schedule)

    def update_schedule(self, schedule_id, schedule):
        return self.call('schedule', 'patch', obj=schedule_id,
                         data=schedule)

    def delete_schedule(self, schedule_id):
        # Schedule messages must all be deleted first for FK reasons
        return self.call('schedule', 'delete', obj=schedule_id)
