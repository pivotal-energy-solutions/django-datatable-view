# -*- encoding: utf-8 -*-

from django.conf.urls import include, url
try:
    # Django < 1.10
    from django.conf.urls import patterns
except ImportError:
    def patterns(prefix, *urls):
        return list(urls)

urlpatterns = patterns('',
    url(r'^', include('example_project.example_app.urls')),
)
