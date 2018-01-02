# -*- encoding: utf-8 -*-

import json

import django
from django.urls import reverse

import six

from .testcase import DatatableViewTestCase
from .example_project.example_project.example_app import views
from .example_project.example_project.example_app import models


if django.VERSION < (1, 7):
    initial_data_fixture = 'initial_data_legacy.json'
elif django.VERSION < (1, 10):
    initial_data_fixture = 'initial_data_17.json'
else:
    initial_data_fixture = 'initial_data_modern.json'


class FakeRequest(object):
    def __init__(self, url, method='GET'):
        self.path = url
        self.method = method
        setattr(self, method, {})


class ViewsTests(DatatableViewTestCase):
    urls = 'datatableview.tests.example_project.example_project.example_app.urls'

    fixtures = [initial_data_fixture]

    def get_json_response(self, url):
        response = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        content = response.content
        if six.PY3:
            content = content.decode()
        return json.loads(content)

    def test_zero_configuration_datatable_view(self):
        """ Verifies that no column definitions means all local fields are used. """
        view = views.ZeroConfigurationDatatableView
        url = reverse('zero-configuration')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        self.assertEqual(
            len(list(response.context['datatable'])),
            len(models.Entry._meta.local_fields)
        )

    def test_specific_columns_datatable_view(self):
        """ Verifies that "columns" list matches context object length. """
        view = views.SpecificColumnsDatatableView()
        url = reverse('specific-columns')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        self.assertEqual(
            len(list(response.context['datatable'])),
            len(view.get_datatable().columns)
        )

    def test_pretty_names_datatable_view(self):
        """ Verifies that a pretty name definition is used instead of the verbose name. """
        view = views.PrettyNamesDatatableView()
        url = reverse('pretty-names')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        self.assertEqual(
            len(list(response.context['datatable'])),
            len(view.get_datatable().columns)
        )
        self.assertEqual(response.context['datatable'].columns['pub_date'].label, "Publication date")

    # def test_x_editable_columns_datatable_view(self):
    #     view = views.XEditableColumnsDatatableView
    #     url = reverse('x-editable-columns')
    #     response = self.client.get(url)

    def test_customized_template_datatable_view(self):
        """
        Verify that the custom structure template is getting rendered instead of the default one.
        """
        view = views.CustomizedTemplateDatatableView()
        url = reverse('customized-template')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        self.assertContains(response, """<table class="table table-striped table-bordered datatable" """)

    def test_bootstrap_template_datatable_view(self):
        """
        Verify that the custom structure template is getting rendered instead of the default one.
        """
        view = views.BootstrapTemplateDatatableView()
        url = reverse('bootstrap-template')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        self.assertContains(response, """<table class="display datatable table table-striped table-bordered" """)

    def test_multiple_tables_datatable_view(self):
        view = views.MultipleTablesDatatableView()
        url = reverse('multiple-tables')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        self.assertIn('demo1_datatable', response.context)
        self.assertIn('demo2_datatable', response.context)
        self.assertIn('demo3_datatable', response.context)

        demo1_obj = self.get_json_response(str(url) + "?datatable=demo1")
        self.assertEqual(len(demo1_obj['data'][0]), 2 + 2)  # 2 built-in DT items
        demo2_obj = self.get_json_response(str(url) + "?datatable=demo2")
        self.assertEqual(len(demo2_obj['data'][0]), 1 + 2)  # 2 built-in DT items
        demo3_obj = self.get_json_response(str(url) + "?datatable=demo3")
        self.assertEqual(len(demo3_obj['data'][0]), 3 + 2)  # 2 built-in DT items

    def test_embedded_table_datatable_view(self):
        view = views.SatelliteDatatableView()
        url = reverse('embedded-table')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        self.assertEqual(
            len(list(response.context['datatable'])),
            len(view.get_datatable().columns)
        )


    # Straightforward views that call on procedural logic not worth testing.  We would effectively
    # be proving that Python strings concatenate, etc.
    # Instead of proving details of the callbacks we've written, we'll just ask for the views, to
    # make certain that they don't generate errors.

    def test_column_backed_by_method_datatable_view(self):
        view = views.ColumnBackedByMethodDatatableView
        url = reverse('column-backed-by-method')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        obj = self.get_json_response(url)

    def test_compound_columns_datatable_view(self):
        view = views.CompoundColumnsDatatableView
        url = reverse('compound-columns')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        obj = self.get_json_response(url)

    def test_many_to_many_fields_datatable_view(self):
        view = views.ManyToManyFieldsDatatableView
        url = reverse('many-to-many-fields')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        obj = self.get_json_response(url)

    def test_default_callback_names_datatable_view(self):
        view = views.DefaultCallbackNamesDatatableView
        url = reverse('default-callback-names')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        obj = self.get_json_response(url)

    def test_helpers_reference_datatable_view(self):
        view = views.HelpersReferenceDatatableView
        url = reverse('helpers-reference')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        obj = self.get_json_response(url)

    def test_satellite_datatable_view(self):
        view = views.SatelliteDatatableView
        url = reverse('satellite')
        view.request = FakeRequest(url)
        response = self.client.get(url)
        obj = self.get_json_response(url)
