# -*- encoding: utf-8 -*-

from django.conf.urls import patterns, include, url

urlpatterns = patterns('',
    url(r'^', include('example_project.example_app.urls')),
)
