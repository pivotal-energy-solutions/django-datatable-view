import re

from django.db.models import Model, Manager
from django.core.exceptions import ObjectDoesNotExist
from django.forms.util import flatatt
from django.template.loader import render_to_string
try:
    from django.utils.encoding import python_2_unicode_compatible
except ImportError:
    from .compat import python_2_unicode_compatible

import six

from .utils import (normalize_config, apply_options, get_field_definition, ColumnInfoTuple,
                    ColumnOrderingTuple)

class DatatableOptions(object):
    def __init__(self, options=None):
        self.columns = getattr(options, 'columns', None)  # table headers
        self.ordering = getattr(options, 'ordering', None)  # override to Model._meta.ordering
        self.start_offset = getattr(options, 'start_offset', None)  # results to skip ahead
        self.page_length = getattr(options, 'page_length', 25)  # length of a single result page
        self.search = getattr(options, 'search', None)  # client search string
        self.search_fields = getattr(options, 'search_fields', None)  # extra searchable ORM fields
        self.unsortable_columns = getattr(options, 'unsortable_columns', None)
        self.hidden_columns = getattr(options, 'hidden_columns', None)  # generated, but hidden
        self.structure_template = getattr(options, 'structure_template', "datatableview/default_structure.html")

        self.result_counter_id = getattr(options, 'result_counter_id', 'id_count')


class DatatableMetaclass(type):
    def __new__(cls, name, bases, attrs):
        new_class = super(DatatableMetaclass, cls).__new__(cls, name, bases, attrs)
        new_class._meta = DatatableOptions(getattr(new_class, 'Meta', None))
        return new_class


class BaseDatatable(object, six.with_metaclass(DatatableMetaclass)):
    def __init__(self, object_list, url, view=None, model=None, query_config=None, **kwargs):
        self.object_list = object_list
        self.url = url
        self.view = view
        self.model = model
        self.configure(self._meta.__dict__, kwargs, query_config)

        self.total_initial_record_count = None
        self.unpaged_record_count = None

    def configure(self, meta_config, view_config, query_config):
        declared_config = dict(meta_config, **view_config)
        self.config = normalize_config(declared_config, query_config, model=self.model)

        # Core options, not modifiable by client updates
        if self.config.get('columns') is None:
            model_fields = self.model._meta.local_fields
            self.config['columns'] = list(map(lambda f: (six.text_type(f.verbose_name), f.name), model_fields))

        if self.config.get('hidden_columns') is None:
            self.config['hidden_columns'] = []

        if self.config.get('search_fields') is None:
            self.config['search_fields'] = []

        if self.config.get('unsortable_columns') is None:
            self.config['unsortable_columns'] = []

        self._flat_column_names = []
        for column in self.config['columns']:
            column = get_field_definition(column)
            flat_name = column.pretty_name
            if column.fields:
                flat_name = column.fields[0]
            self._flat_column_names.append(flat_name)

        self.ordering = {}
        if self.config['ordering']:
            for i, name in enumerate(self.config['ordering']):
                plain_name = name.lstrip('-+')
                index = self.get_column_index(plain_name)
                if index == -1:
                    continue
                sort_direction = 'desc' if name[0] == '-' else 'asc'
                self.ordering[plain_name] = ColumnOrderingTuple(i, index, sort_direction)

    # Data retrieval
    def get_column_index(self, name):
        if name.startswith('!'):
            return int(name[1:])
        try:
            return self._flat_column_names.index(name)
        except ValueError:
            return -1

    def _get_current_page(self):
        """
        If page_length is specified in the options or AJAX request, the result list is shortened to
        the correct offset and length.  Paged or not, the finalized object_list is then returned.
        """

        # Narrow the results to the appropriate page length for serialization
        if self.config['page_length'] != -1:
            i_begin = self.config['start_offset']
            i_end = self.config['start_offset'] + self.config['page_length']
            object_list = self._records[i_begin:i_end]

        return object_list

    def get_records(self):
        if not hasattr(self, '_records'):
            self.populate_records()

        return [self.get_record_data(obj) for obj in self._get_current_page()]

    def populate_records(self):
        self._records = apply_options(self.object_list, self)

    def preload_record_data(self, instance):
        """
        An empty hook for letting the view do something with ``instance`` before column lookups are
        called against the object.  The tuple of items returned will be passed as positional
        arguments to any of the ``get_column_FIELD_NAME_data()`` methods.

        """

        return ()

    def _get_preloaded_data(self, instance):
        """
        Fetches value from ``preload_record_data()``.

        If a single value is returned and it is not a dict, list or tuple, it is made into a tuple.
        The tuple will be supplied to the resolved method as ``*args``.

        If the returned value is already a list/tuple, it will also be sent as ``*args``.

        If the returned value is a dict, it will be sent as ``**kwargs``.

        The two types cannot be mixed.

        """
        preloaded_data = self.preload_record_data(instance)
        if isinstance(preloaded_data, dict):
            preloaded_args = ()
            preloaded_kwargs = preloaded_data
        elif isinstance(preloaded_data, (tuple, list)):
            preloaded_args = preloaded_data
            preloaded_kwargs = {}
        else:
            preloaded_args = (preloaded_data,)
            preloaded_kwargs = {}
        return preloaded_args, preloaded_kwargs

    def get_record_data(self, obj):
        """
        Returns a list of column data intended to be passed directly back to dataTables.js.

        Each column generates a 2-tuple of data. [0] is the data meant to be displayed to the client
        and [1] is the data in plain-text form, meant for manual searches.  One wouldn't want to
        include HTML in [1], for example.

        """

        data = {
            'pk': obj.pk,
            '_extra_data': {},  # TODO: callback structure for user access to this field
        }
        for i, name in enumerate(self.config['columns']):
            column_data = self.get_column_data(i, name, obj)[0]
            if six.PY2 and isinstance(column_data, str):  # not unicode
                column_data = column_data.decode('utf-8')
            data[str(i)] = six.text_type(column_data)
        return data

    def get_column_data(self, i, name, instance):
        """ Finds the backing method for column ``name`` and returns the generated data. """
        column = get_field_definition(name)
        is_custom, f = self._get_resolver_method(i, column)
        if is_custom:
            args, kwargs = self._get_preloaded_data(instance)
            try:
                kwargs['default_value'] = self._get_column_data_default(instance, column)[1]
            except AttributeError:
                kwargs['default_value'] = None
            kwargs['field_data'] = name
            kwargs['view'] = self.view
            values = f(instance, *args, **kwargs)
        else:
            values = f(instance, column)

        if not isinstance(values, (tuple, list)):
            if six.PY2:
                if isinstance(values, str):  # not unicode
                    values = values.decode('utf-8')
                else:
                    values = unicode(values)
            values = (values, re.sub(r'<[^>]+>', '', six.text_type(values)))

        return values

    def _get_resolver_method(self, i, column):
        """
        Using a slightly mangled version of the column's name (explained below) each column's value
        is derived.

        Each field can generate customized data by defining a method on the view called either
        "get_column_FIELD_NAME_data" or "get_column_INDEX_data".

        If the FIELD_NAME approach is used, the name is the raw field name (e.g., "street_name") or
        else the friendly representation defined in a 2-tuple such as
        ("Street name", "subdivision__home__street_name"), where the name has non-alphanumeric
        characters stripped to single underscores.  For example, the friendly name
        "Region: Subdivision Type" would convert to "Region_Subdivision_Type", requiring the method
        name "get_column_Region_Subdivision_Type_data".

        Alternatively, if the INDEX approach is used, a method will be fetched called
        "get_column_0_data", or otherwise using the 0-based index of the column's position as
        defined in the view's ``datatable_options['columns']`` setting.

        Finally, if a third element is defined in the tuple, it will be treated as the function or
        name of a member attribute which will be used directly.

        """

        callback = column.callback
        if callback:
            if callable(callback):
                return True, callback
            return True, getattr(self, callback)

        # Treat the 'nice name' as the starting point for looking up a method
        name = column.pretty_name
        if not name:
            name = column.fields[0]

        mangled_name = re.sub(r'[\W_]+', '_', name)

        f = getattr(self, 'get_column_%s_data' % mangled_name, None)
        if f:
            return True, f

        f = getattr(self, 'get_column_%d_data' % i, None)
        if f:
            return True, f

        return False, self._get_column_data_default

    def _get_column_data_default(self, instance, column, *args, **kwargs):
        """ Default mechanism for resolving ``column`` through the model instance ``instance``. """

        def chain_lookup(obj, bit):
            try:
                value = getattr(obj, bit)
            except (AttributeError, ObjectDoesNotExist):
                value = None
            else:
                if callable(value):
                    if isinstance(value, Manager):
                        pass
                    elif not hasattr(value, 'alters_data') or value.alters_data is not True:
                        value = value()
            return value

        values = []
        for field_name in column.fields:
            value = reduce(chain_lookup, [instance] + field_name.split('__'))

            if isinstance(value, Model):
                value = six.text_type(value)

            if value is not None:
                values.append(value)

        if len(values) == 1:
            value = values[0]
        else:
            value = u' '.join(map(six.text_type, values))

        return value, value


@python_2_unicode_compatible
class Datatable(BaseDatatable):
    # Template rendering features
    def __str__(self):
        context = {
            'url': self.url,
            'result_counter_id': self.config['result_counter_id'],
            'column_info': self.get_column_info(),
        }
        return render_to_string(self.config['structure_template'], context)

    def __iter__(self):
        """
        Yields a 2-tuple for each column in the form ("Column Name", " data-attribute='asdf'"),
        """

        for column_info in self.get_column_info():
            yield column_info

    def get_column_info(self):
        """
        Returns an iterable of 2-tuples in the form

            ("Pretty name", ' data-bSortable="true"',)

        """

        column_info = []
        if self.model:
            model_fields = self.model._meta.get_all_field_names()
        else:
            model_fields = []

        for column in self.config['columns']:
            column = get_field_definition(column)
            pretty_name = column.pretty_name
            column_name = column.pretty_name
            if column.fields and column.fields[0] in model_fields:
                ordering_name = column.fields[0]
                if not pretty_name:
                    field = self.model._meta.get_field_by_name(column.fields[0])[0]
                    column_name = field.name
                    pretty_name = field.verbose_name
            else:
                ordering_name = pretty_name

            attributes = self.get_column_attributes(ordering_name)
            column_info.append(ColumnInfoTuple(pretty_name, flatatt(attributes)))

        return column_info

    def get_column_attributes(self, name):
        javascript_boolean = {
            True: 'true',
            False: 'false',
        }
        attributes = {
            'data-sortable': javascript_boolean[name not in self.config['unsortable_columns']],
            'data-visible': javascript_boolean[name not in self.config['hidden_columns']],
        }

        if name in self.ordering:
            attributes['data-sorting'] = ','.join(map(six.text_type, self.ordering[name]))

        return attributes
