# from django.test import TestCase
from django.test.utils import override_settings

from .testcase import DatatableViewTestCase
from .test_app import models
from .. import utils

def get_structure(columns, opts):
    return utils.get_datatable_structure('/', models.ExampleModel, dict(opts, columns=columns))

@override_settings(INSTALLED_APPS=['datatableview.tests.test_app'])
class UtilsTests(DatatableViewTestCase):
    def test_get_first_orm_bit(self):
        """  """
        self.assertEqual(utils.get_first_orm_bit('field'), 'field')
        self.assertEqual(utils.get_first_orm_bit('field__otherfield'), 'field')
        self.assertEqual(utils.get_first_orm_bit(["Pretty Name", 'field']), 'field')
        self.assertEqual(utils.get_first_orm_bit(["Pretty Name", 'field', "callback"]), 'field')
        self.assertEqual(utils.get_first_orm_bit(["Pretty Name", 'field__otherfield']), 'field')
        self.assertEqual(utils.get_first_orm_bit(["Pretty Name", 'field__otherfield', "callback"]), 'field')

    def test_resolve_orm_path_local(self):
        """ Verifies that references to a local field on a model are returned. """
        field = utils.resolve_orm_path(models.ExampleModel, 'name')
        self.assertEqual(field, models.ExampleModel._meta.get_field_by_name('name')[0])

    def test_resolve_orm_path_fk(self):
        """ Verify that ExampleModel->RelatedModel.name == RelatedModel.name """
        remote_field = utils.resolve_orm_path(models.ExampleModel, 'related__name')
        self.assertEqual(remote_field, models.RelatedModel._meta.get_field_by_name('name')[0])

    def test_resolve_orm_path_reverse_fk(self):
        """ Verify that ExampleModel->>>ReverseRelatedModel.name == ReverseRelatedModel.name """
        remote_field = utils.resolve_orm_path(models.ExampleModel, 'reverserelatedmodel__name')
        self.assertEqual(remote_field, models.ReverseRelatedModel._meta.get_field_by_name('name')[0])

    def test_resolve_orm_path_m2m(self):
        """ Verify that ExampleModel->>>RelatedM2MModel.name == RelatedM2MModel.name """
        remote_field = utils.resolve_orm_path(models.ExampleModel, 'relateds__name')
        self.assertEqual(remote_field, models.RelatedM2MModel._meta.get_field_by_name('name')[0])

    def test_split_real_fields(self):
        """ Verifies that the first non-real field causes a break in the field list. """
        model = models.ExampleModel

        # All-real fields
        real, fake = utils.split_real_fields(model, ['name', 'date_created'])
        self.assertEqual(real, ['name', 'date_created'])
        self.assertEqual(fake, [])

        # No real fields
        real, fake = utils.split_real_fields(model, ['fake1', 'fake2'])
        self.assertEqual(real, [])
        self.assertEqual(fake, ['fake1', 'fake2'])

        # Real first, fake last
        real, fake = utils.split_real_fields(model, ['name', 'fake'])
        self.assertEqual(real, ['name'])
        self.assertEqual(fake, ['fake'])
        
        # Fake first, real last
        real, fake = utils.split_real_fields(model, ['fake', 'name'])
        self.assertEqual(real, [])
        self.assertEqual(fake, ['fake', 'name'])
        
    def test_filter_real_fields(self):
        model = models.ExampleModel
        fields = [
            'name',
            ('name',),
            ("Pretty Name", 'name'),
            ("Pretty Name", 'name', 'callback'),
        ]
        fakes = [
            'fake',
            ("Pretty Name", 'fake'),
            ("Pretty Name", 'fake', 'callback'),
            None,
            ("Pretty Name", None),
            ("Pretty Name", None, 'callback'),
        ]
        db_fields, virtual_fields = utils.filter_real_fields(model, fields + fakes,
                                                             key=utils.get_first_orm_bit)

        self.assertEqual(db_fields, fields)
        self.assertEqual(virtual_fields, fakes)

    def test_structure_ordering(self):
        """ Verifies that the structural object correctly maps configuration values. """
        # Verify basic ordering
        columns = [
            'name',
        ]
        structure = get_structure(columns, { 'ordering': ['name'] })
        self.assertEqual(structure.ordering['name'].direction, 'asc')
        structure = get_structure(columns, { 'ordering': ['+name'] })
        self.assertEqual(structure.ordering['name'].direction, 'asc')
        structure = get_structure(columns, { 'ordering': ['-name'] })
        self.assertEqual(structure.ordering['name'].direction, 'desc')

        # Verify compound ordering is preserved
        columns = [
            'pk',
            'name',
        ]
        structure = get_structure(columns, { 'ordering': ['name', 'pk'] })
        self.assertEqual(structure.ordering['name'].order, 0)
        self.assertEqual(structure.ordering['pk'].order, 1)

        # Verify non-real field ordering is recognized when column is defined
        columns = [
            'fake',
        ]
        structure = get_structure(columns, { 'ordering': ['fake'] })
        self.assertEqual(structure.ordering['fake'].direction, 'asc')
        structure = get_structure(columns, { 'ordering': ['+fake'] })
        self.assertEqual(structure.ordering['fake'].direction, 'asc')
        structure = get_structure(columns, { 'ordering': ['-fake'] })
        self.assertEqual(structure.ordering['fake'].direction, 'desc')

        # Verify invalid ordering names are not included
        columns = [
            'name',
        ]
        structure = get_structure(columns, { 'ordering': ['fake', 'name'] })
        self.assertIn('name', structure.ordering)
        self.assertNotIn('fake', structure.ordering)

    def test_structure_data_api(self):
        """
        Verifies that unsortable_columns, hidden_columns, and ordering all add expected data-* API
        attributes
        """
        columns = [
            'pk',
            'name',
        ]
        structure = get_structure(columns, {})
        self.assertEqual(structure.get_column_attributes('name')['data-visible'], 'true')
        self.assertEqual(structure.get_column_attributes('name')['data-sortable'], 'true')
        structure = get_structure(columns, { 'hidden_columns': ['name'] })
        self.assertEqual(structure.get_column_attributes('name')['data-visible'], 'false')
        self.assertEqual(structure.get_column_attributes('name')['data-sortable'], 'true')
        structure = get_structure(columns, { 'unsortable_columns': ['name'] })
        self.assertEqual(structure.get_column_attributes('name')['data-visible'], 'true')
        self.assertEqual(structure.get_column_attributes('name')['data-sortable'], 'false')
        structure = get_structure(columns, { 'hidden_columns': ['name'], 'unsortable_columns': ['name'] })
        self.assertEqual(structure.get_column_attributes('name')['data-visible'], 'false')
        self.assertEqual(structure.get_column_attributes('name')['data-sortable'], 'false')
        structure = get_structure(columns, { 'ordering': ['-name', 'pk'] })
        self.assertEqual(structure.get_column_attributes('pk')['data-sorting'], '1,0,asc')
        self.assertEqual(structure.get_column_attributes('name')['data-sorting'], '0,1,desc')

    def test_structure_automatic_pretty_names(self):
        """ Verify columns missing Pretty Names receive one based on their field name. """
        columns = [
            ('Primary Key', 'pk'),
            'name',
        ]
        structure = get_structure(columns, {})
        column_info = structure.get_column_info()
        self.assertEqual(column_info[0].pretty_name, "Primary Key")
        self.assertEqual(column_info[1].pretty_name, "Name")

    def test_structure_is_iterable(self):
        columns = [
            'pk',
            'name',
            'fake',
        ]
        structure = get_structure(columns, {})
        self.assertEqual(len(list(structure)), len(columns))
