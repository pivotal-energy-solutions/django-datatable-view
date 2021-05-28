# -*- coding: utf-8 -*-

from django import template
from django import get_version
from django.urls import reverse

register = template.Library()

if get_version().split(".") < ["1", "5"]:

    @register.simple_tag(name="url")
    def django_1_4_url_simple(url_name):
        return reverse(url_name)
