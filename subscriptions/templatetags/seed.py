from django import template

import seed_stage_based_messaging

register = template.Library()


@register.simple_tag
def current_version():
    return seed_stage_based_messaging.__version__
