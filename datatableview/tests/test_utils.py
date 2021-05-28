# -*- coding: utf-8 -*-
from django.apps import apps

from datatableview.columns import Column
from .testcase import DatatableViewTestCase
from datatableview.utils import get_first_orm_bit, resolve_orm_path

ExampleModel = apps.get_model("test_app", "ExampleModel")
RelatedModel = apps.get_model("test_app", "RelatedModel")
RelatedM2MModel = apps.get_model("test_app", "RelatedM2MModel")
ReverseRelatedModel = apps.get_model("test_app", "ReverseRelatedModel")


class UtilsTests(DatatableViewTestCase):
    def test_get_first_orm_bit(self):
        """ """
        self.assertEqual(get_first_orm_bit(Column(sources=["field"])), "field")
        self.assertEqual(get_first_orm_bit(Column(sources=["field__otherfield"])), "field")

    def test_resolve_orm_path_local(self):
        """Verifies that references to a local field on a model are returned."""
        field = resolve_orm_path(ExampleModel, "name")
        self.assertEqual(field, ExampleModel._meta.get_field("name"))

    def test_resolve_orm_path_fk(self):
        """Verify that ExampleModel->RelatedModel.name == RelatedModel.name"""
        remote_field = resolve_orm_path(ExampleModel, "related__name")
        self.assertEqual(remote_field, RelatedModel._meta.get_field("name"))

    def test_resolve_orm_path_reverse_fk(self):
        """Verify that ExampleModel->>>ReverseRelatedModel.name == ReverseRelatedModel.name"""
        remote_field = resolve_orm_path(ExampleModel, "reverserelatedmodel__name")
        self.assertEqual(remote_field, ReverseRelatedModel._meta.get_field("name"))

    def test_resolve_orm_path_m2m(self):
        """Verify that ExampleModel->>>RelatedM2MModel.name == RelatedM2MModel.name"""
        remote_field = resolve_orm_path(ExampleModel, "relateds__name")
        self.assertEqual(remote_field, RelatedM2MModel._meta.get_field("name"))
