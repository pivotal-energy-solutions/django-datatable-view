# -*- encoding: utf-8 -*-

import re

try:
    from django.urls import url
except ImportError:
    from django.conf.urls import url

from . import views

urls = []
for attr in dir(views):
    View = getattr(views, attr)
    try:
        is_demo = issubclass(View, views.DemoMixin) and View is not views.DemoMixin
    except TypeError:
        continue
    if is_demo:
        name = re.sub(r'([a-z]|[A-Z]+)(?=[A-Z])', r'\1-', attr).lower()
        name = name.replace("-datatable-view", "")
        urls.append(url(r'^{name}/$'.format(name=name), View.as_view(), name=name))

urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name="index"),
    url(r'^reset/$', views.ResetView.as_view()),
    url(r'^migration-guide/$', views.MigrationGuideView.as_view(), name="migration-guide"),
    url(r'^column-formats/$', views.ValidColumnFormatsView.as_view(), name="column-formats"),
    url(r'^javascript-initialization/$', views.JavascriptInitializationView.as_view(), name="js-init"),
    url(r'^satellite/$', views.SatelliteDatatableView.as_view(), name="satellite"),
] + urls
