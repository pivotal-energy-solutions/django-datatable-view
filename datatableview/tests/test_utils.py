# from django.test import TestCase
from django.test.utils import override_settings

from .testcase import DatatableViewTestCase
from .test_app import models
from .. import utils

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
