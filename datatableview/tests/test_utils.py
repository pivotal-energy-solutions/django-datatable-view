# -*- encoding: utf-8 -*-

from .testcase import DatatableViewTestCase
from .test_app import models
from ..columns import Column
from ..views.legacy import DEFAULT_OPTIONS
from .. import utils


class UtilsTests(DatatableViewTestCase):
    def test_get_first_orm_bit(self):
        """  """
        self.assertEqual(utils.get_first_orm_bit(Column(sources=['field'])), 'field')
        self.assertEqual(utils.get_first_orm_bit(Column(sources=['field__otherfield'])), 'field')

    def test_resolve_orm_path_local(self):
        """ Verifies that references to a local field on a model are returned. """
        field = utils.resolve_orm_path(models.ExampleModel, 'name')
        self.assertEqual(field, models.ExampleModel._meta.get_field('name'))

    def test_resolve_orm_path_fk(self):
        """ Verify that ExampleModel->RelatedModel.name == RelatedModel.name """
        remote_field = utils.resolve_orm_path(models.ExampleModel, 'related__name')
        self.assertEqual(remote_field, models.RelatedModel._meta.get_field('name'))

    def test_resolve_orm_path_reverse_fk(self):
        """ Verify that ExampleModel->>>ReverseRelatedModel.name == ReverseRelatedModel.name """
        remote_field = utils.resolve_orm_path(models.ExampleModel, 'reverserelatedmodel__name')
        self.assertEqual(remote_field, models.ReverseRelatedModel._meta.get_field('name'))

    def test_resolve_orm_path_m2m(self):
        """ Verify that ExampleModel->>>RelatedM2MModel.name == RelatedM2MModel.name """
        remote_field = utils.resolve_orm_path(models.ExampleModel, 'relateds__name')
        self.assertEqual(remote_field, models.RelatedM2MModel._meta.get_field('name'))
