# -*- coding: utf-8 -*-

import re

from django.urls import re_path

from . import views

urls = []
for attr in dir(views):
    View = getattr(views, attr)
    try:
        is_demo = issubclass(View, views.DemoMixin) and View is not views.DemoMixin
    except TypeError:
        continue
    if is_demo:
        name = re.sub(r"([a-z]|[A-Z]+)(?=[A-Z])", r"\1-", attr).lower()
        name = name.replace("-datatable-view", "")
        urls.append(re_path(r"^{name}/$".format(name=name), View.as_view(), name=name))

urlpatterns = [
    re_path(r"^$", views.IndexView.as_view(), name="index"),
    re_path(r"^reset/$", views.ResetView.as_view()),
    re_path(r"^migration-guide/$", views.MigrationGuideView.as_view(), name="migration-guide"),
    re_path(r"^column-formats/$", views.ValidColumnFormatsView.as_view(), name="column-formats"),
    re_path(
        r"^javascript-initialization/$",
        views.JavascriptInitializationView.as_view(),
        name="js-init",
    ),
    re_path(r"^satellite/$", views.SatelliteDatatableView.as_view(), name="satellite"),
] + urls
