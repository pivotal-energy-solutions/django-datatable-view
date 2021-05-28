# -*- coding: utf-8 -*-

import logging
from collections import namedtuple

from django.views.generic.list import ListView

from .base import DatatableMixin
from ..datatables import LegacyDatatable

log = logging.getLogger(__name__)

FieldDefinitionTuple = namedtuple("FieldDefinitionTuple", ["pretty_name", "fields", "callback"])
ColumnOrderingTuple = namedtuple("ColumnOrderingTuple", ["order", "column_index", "direction"])
ColumnInfoTuple = namedtuple("ColumnInfoTuple", ["pretty_name", "attrs"])

DEFAULT_OPTIONS = {
    "columns": [],  # table headers
    "ordering": [],  # override to Model._meta.ordering
    "start_offset": 0,  # results to skip ahead
    "page_length": 25,  # length of a single result page
    "search": "",  # client search string
    "search_fields": [],  # extra ORM paths to search; not displayed
    "unsortable_columns": [],  # table headers not allowed to be sorted
    "hidden_columns": [],  # table headers to be generated, but hidden by the client
    "structure_template": "datatableview/legacy_structure.html",
    "result_counter_id": "id_count",  # HTML element ID to display the total results
}


def get_field_definition(field_definition):
    """Normalizes a field definition into its component parts, even if some are missing."""
    if not isinstance(field_definition, (tuple, list)):
        field_definition = [field_definition]
    else:
        field_definition = list(field_definition)

    if len(field_definition) == 1:
        field = [None, field_definition, None]
    elif len(field_definition) == 2:
        field = field_definition + [None]
    elif len(field_definition) == 3:
        field = field_definition
    else:
        raise ValueError("Invalid field definition format.")

    if not isinstance(field[1], (tuple, list)):
        field[1] = (field[1],)
    field[1] = tuple(name for name in field[1] if name is not None)

    return FieldDefinitionTuple(*field)


class LegacyDatatableMixin(DatatableMixin):
    """
    Modern :py:class:`DatatableView` mechanisms simply powered by the old configuration style.  Use
    this if you can. If you get errors and you've been overriding things on the old DatatableView,
    fall back to using ``LegacyDatatableView``, which provides those old hooks.

    The :py:meth:`.get_datatable_options` hook is still respected as the getter for runtime
    configuration, but it will be broken up into keyword arguments to be forwarded to its
    :py:class:`~datatableview.datatables.Datatable`, which in this case is a
    :py:class:`~datatableview.datatables.LegacyDatatable`.
    """

    datatable_options = None
    datatable_class = LegacyDatatable

    def get_datatable_options(self):
        return self.datatable_options

    def _get_datatable_options(self):
        """Helps to keep the promise that we only run ``get_datatable_options()`` once."""
        if not hasattr(self, "_datatable_options"):
            self._datatable_options = self.get_datatable_options()

            # Convert sources from list to tuple, so that modern Column tracking dicts can hold the
            # field definitions as keys.
            columns = self._datatable_options.get("columns", [])
            for i, column in enumerate(columns):
                if len(column) >= 2 and isinstance(column[1], list):
                    column = list(column)
                    column[1] = tuple(column[1])
                    columns[i] = tuple(column)

        return self._datatable_options

    def get_datatable_kwargs(self, **kwargs):
        kwargs = super(LegacyDatatableMixin, self).get_datatable_kwargs(**kwargs)
        kwargs["callback_target"] = self
        kwargs.update(self._get_datatable_options())
        return kwargs

    def preload_record_data(self, obj):
        return {}

    def get_extra_record_data(self, obj):
        return {}


class LegacyDatatableView(LegacyDatatableMixin, ListView):
    """
    Implements :py:class:`LegacyDatatableMixin` and the standard Django ``ListView``.
    """
