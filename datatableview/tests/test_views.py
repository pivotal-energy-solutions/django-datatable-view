import json

from django.core.urlresolvers import reverse

from .testcase import DatatableViewTestCase
from .example_project.example_project.example_app import views
from .example_project.example_project.example_app import models

class ViewsTests(DatatableViewTestCase):
    urls = 'datatableview.tests.example_project.example_project.example_app.urls'

    def get_json_response(self, url):
        response = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        return json.loads(response.content)

    def test_zero_configuration_datatable_view(self):
        """ Verifies that no column definitions means all local fields are used. """
        view = views.ZeroConfigurationDatatableView
        url = reverse('zero-configuration')
        response = self.client.get(url)
        self.assertEqual(
            len(list(response.context['datatable'])),
            len(models.Entry._meta.local_fields)
        )

    def test_specific_columns_datatable_view(self):
        """ Verifies that "columns" list matches context object length. """
        view = views.SpecificColumnsDatatableView
        url = reverse('specific-columns')
        response = self.client.get(url)
        self.assertEqual(
            len(list(response.context['datatable'])),
            len(view.datatable_options['columns'])
        )

    def test_pretty_names_datatable_view(self):
        """ Verifies that a pretty name definition is used instead of the verbose name. """
        view = views.PrettyNamesDatatableView
        url = reverse('pretty-names')
        response = self.client.get(url)
        self.assertEqual(
            len(list(response.context['datatable'])),
            len(view.datatable_options['columns'])
        )
        data = dict(response.context['datatable'])
        self.assertIn("Publication date", data)
        self.assertNotIn("pub date", data)

    def test_presentational_changes_datatable_view(self):
        """ Verifies that a custom callback is used to modify the appearance of the field. """
        view = views.PresentationalChangesDatatableView
        url = reverse('presentational-changes')
        obj = self.get_json_response(url)
        row = obj['aaData'][0]
        columns = view.datatable_options['columns']
        index_age = columns.index([c for c in columns if c[0] == "Age"][0])
        index_pub_date = columns.index([c for c in columns if c[0] == "Publication date"][0])
        self.assertNotEqual(row[str(index_age)], row[str(index_pub_date)])

    def test_virtual_column_definitions_datatable_view(self):
        view = views.VirtualColumnDefinitionsDatatableView
        url = reverse('virtual-column-definitions')
        obj = self.get_json_response(url)
        row = obj['aaData'][0]
        columns = view.datatable_options['columns']
        index_age = columns.index([c for c in columns if c[0] == "Age"][0])
        self.assertNotEqual(row[str(index_age)], "")

    # def test_x_editable_columns_datatable_view(self):
    #     view = views.XEditableColumnsDatatableView
    #     url = reverse('x-editable-columns')
    #     response = self.client.get(url)

    def test_ordering_datatable_view(self):
        view = views.OrderingDatatableView
        url = reverse('ordering')
        response = self.client.get(url)
        attrs = dict(response.context['datatable'])["Pretty name"]
        self.assertIn('data-sortable="true"', attrs)
        self.assertIn('data-sorting="0,0,desc"', attrs)

    def test_unsortable_columns_datatable_view(self):
        view = views.UnsortableColumnsDatatableView
        url = reverse('unsortable-columns')
        response = self.client.get(url)

        for unsortable_column in ["headline", 'blog', 'pub date']:
            attrs = dict(response.context['datatable'])[unsortable_column]
            self.assertIn('data-sortable="false"', attrs)

    def test_hidden_columns_datatable_view(self):
        view = views.HiddenColumnsDatatableView
        url = reverse('hidden-columns')
        response = self.client.get(url)
        attrs = dict(response.context['datatable'])["ID"]
        self.assertIn('data-visible="false"', attrs)

    # def test_search_fields_datatable_view(self):
    #     view = views.SearchFieldsDatatableView
    #     url = reverse('search-fields')
    #     response = self.client.get(url)

    def test_customized_template_datatable_view(self):
        """
        Verify that the custom structure template is getting rendered instead of the default one.
        """
        view = views.CustomizedTemplateDatatableView
        url = reverse('customized-template')
        response = self.client.get(url)
        self.assertContains(response, """<table class="table table-striped table-bordered datatable" """)

    def test_bootstrap_template_datatable_view(self):
        """
        Verify that the custom structure template is getting rendered instead of the default one.
        """
        view = views.BootstrapTemplateDatatableView
        url = reverse('bootstrap-template')
        response = self.client.get(url)
        self.assertContains(response, """<table class="table table-striped table-bordered datatable" """)

    def test_multiple_tables_datatable_view(self):
        view = views.MultipleTablesDatatableView
        url = reverse('multiple-tables')
        response = self.client.get(url)
        self.assertIn('modified_columns_datatable', response.context)
        self.assertIn('blog_datatable', response.context)

        demo1_obj = self.get_json_response(url)
        self.assertEqual(len(demo1_obj['aaData'][0]), 3)
        demo2_obj = self.get_json_response(str(url) + "?datatable-type=demo2")
        self.assertEqual(len(demo2_obj['aaData'][0]), 2)
        demo3_obj = self.get_json_response(str(url) + "?datatable-type=demo3")
        self.assertEqual(len(demo3_obj['aaData'][0]), 4)

    def test_embedded_table_datatable_view(self):
        view = views.SatelliteDatatableView
        url = reverse('embedded-table')
        response = self.client.get(url)
        self.assertEqual(
            len(list(response.context['datatable'])),
            len(view.datatable_options['columns'])
        )


    # Straightforward views that call on procedural logic not worth testing.  We would effectively
    # be proving that Python strings concatenate, etc.
    # Instead of proving details of the callbacks we've written, we'll just ask for the views, to
    # make certain that they don't generate errors.

    def test_column_backed_by_method_datatable_view(self):
        view = views.ColumnBackedByMethodDatatableView
        url = reverse('column-backed-by-method')
        response = self.client.get(url)
        obj = self.get_json_response(url)

    def test_compound_columns_datatable_view(self):
        view = views.CompoundColumnsDatatableView
        url = reverse('compound-columns')
        response = self.client.get(url)
        obj = self.get_json_response(url)

    def test_many_to_many_fields_datatable_view(self):
        view = views.ManyToManyFieldsDatatableView
        url = reverse('many-to-many-fields')
        response = self.client.get(url)
        obj = self.get_json_response(url)

    def test_related_fields_datatable_view(self):
        view = views.RelatedFieldsDatatableView
        url = reverse('related-fields')
        response = self.client.get(url)
        obj = self.get_json_response(url)

    def test_default_callback_names_datatable_view(self):
        view = views.DefaultCallbackNamesDatatableView
        url = reverse('default-callback-names')
        response = self.client.get(url)
        obj = self.get_json_response(url)

    def test_helpers_reference_datatable_view(self):
        view = views.HelpersReferenceDatatableView
        url = reverse('helpers-reference')
        response = self.client.get(url)
        obj = self.get_json_response(url)

    def test_satellite_datatable_view(self):
        view = views.SatelliteDatatableView
        url = reverse('satellite')
        response = self.client.get(url)
        obj = self.get_json_response(url)
