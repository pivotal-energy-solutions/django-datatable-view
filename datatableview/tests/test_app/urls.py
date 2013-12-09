from django.conf.urls import patterns, include, url

from . import views

# Views demonstrating core featurse
standard_datatable = patterns('',
    url(r'^simple/$', views.ZeroConfigurationDatatableView.as_view(), name='zeroconfig'),
)

# Views demonstrating xeditable support
xeditable_datatable = patterns('',

)

urlpatterns = patterns('',
    url(r'^$', views.IndexView.as_view(), name="index"),
    url(r'^', include(standard_datatable, namespace='datatable')),
    url(r'^', include(xeditable_datatable, namespace='xeditable')),
)
