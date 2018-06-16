# -*- encoding: utf-8 -*-

from django import template
from django import get_version

register = template.Library()

if get_version().split('.') < ['1', '5']:
    from django.template.defaulttags import url
    from django.urls import reverse

    @register.simple_tag(name="url")
    def django_1_4_url_simple(url_name):
        return reverse(url_name)
