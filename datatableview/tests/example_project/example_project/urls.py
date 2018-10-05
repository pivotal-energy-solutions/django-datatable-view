# -*- encoding: utf-8 -*-

try:
    from django.urls import include, url
except ImportError:
    from django.conf.urls import include, url

urlpatterns = [
    url(r'^', include('example_project.example_app.urls')),
]
