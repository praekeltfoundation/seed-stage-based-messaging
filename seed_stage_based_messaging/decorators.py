import functools

from django.core.exceptions import PermissionDenied


def internal_only(view_func):
    """
    A view decorator which blocks access for requests coming through the load balancer.
    """

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        forwards = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        # The nginx in the docker container adds the loadbalancer IP to the list inside
        # X-Forwarded-For, so if the list contains more than a single item, we know
        # that it went through our loadbalancer
        if len(forwards) > 1:
            raise PermissionDenied()
        return view_func(request, *args, **kwargs)

    return wrapper
