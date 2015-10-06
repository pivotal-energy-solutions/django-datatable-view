# -*- encoding: utf-8 -*-

import re
import copy
import operator
from collections import OrderedDict
try:
    from functools import reduce
except ImportError:
    pass

from django.db import models
from django.template.loader import render_to_string
from django.utils.text import smart_split
try:
    from django.utils.encoding import python_2_unicode_compatible
except ImportError:
    from .compat import python_2_unicode_compatible

import six

from .exceptions import ColumnError, SkipRecord
from . import columns
from .utils import OPTION_NAME_MAP, MINIMUM_PAGE_LENGTH

def pretty_name(name):
    if not name:
        return ''
    return name[0].capitalize() + name[1:]


# Borrowed from the Django forms implementation 
def columns_for_model(model, fields=None, exclude=None, labels=None, processors=None,
                      unsortable=None, hidden=None):
    field_list = []
    opts = model._meta
    for f in sorted(opts.fields):
        if fields is not None and f.name not in fields:
            continue
        if exclude and f.name in exclude:
            continue

        column_class = columns.get_column_for_modelfield(f)
        if labels and f.name in labels:
            label = labels[f.name]
        else:
            label = f.verbose_name
        if processors and f.name in processors:
            processor = processors[f.name]
        else:
            processor = None
        if unsortable and f.name in unsortable:
            sortable = False
        else:
            sortable = True
        if hidden and f.name in hidden:
            visible = False
        else:
            visible = True
        label = (labels or {}).get(f.name, pretty_name(f.verbose_name))
        column = column_class(sources=[f.name], label=label, processor=processor, sortable=sortable,
                              visible=visible)
        column.name = f.name
        field_list.append((f.name, column))

    field_dict = OrderedDict(field_list)
    if fields:
        field_dict = OrderedDict(
            [(f, field_dict.get(f)) for f in fields
                if ((not exclude) or (exclude and f not in exclude))]
        )
    return field_dict

# Borrowed from the Django forms implementation 
def get_declared_columns(bases, attrs, with_base_columns=True):
    """
    Create a list of form field instances from the passed in 'attrs', plus any
    similar fields on the base classes (in 'bases'). This is used by both the
    Form and ModelForm metclasses.

    If 'with_base_columns' is True, all fields from the bases are used.
    Otherwise, only fields in the 'declared_fields' attribute on the bases are
    used. The distinction is useful in ModelForm subclassing.
    Also integrates any additional media definitions
    """
    local_columns = [
        (column_name, attrs.pop(column_name)) \
                for column_name, obj in list(six.iteritems(attrs)) \
                if isinstance(obj, columns.Column)
    ]
    local_columns.sort(key=lambda x: x[1].creation_counter)

    # If this class is subclassing another Form, add that Form's columns.
    # Note that we loop over the bases in *reverse*. This is necessary in
    # order to preserve the correct order of columns.
    if with_base_columns:
        for base in bases[::-1]:
            if hasattr(base, 'base_columns'):
                local_columns = list(six.iteritems(base.base_columns)) + local_columns
    else:
        for base in bases[::-1]:
            if hasattr(base, 'declared_columns'):
                local_columns = list(six.iteritems(base.declared_columns)) + local_columns

    return OrderedDict(local_columns)

class DatatableOptions(object):
    def __init__(self, options=None):
        self.model = getattr(options, 'model', None)
        self.columns = getattr(options, 'columns', None)  # table headers
        self.exclude = getattr(options, 'exclude', None)
        self.ordering = getattr(options, 'ordering', None)  # override to Model._meta.ordering
        # self.start_offset = getattr(options, 'start_offset', None)  # results to skip ahead
        self.page_length = getattr(options, 'page_length', 25)  # length of a single result page
        # self.search = getattr(options, 'search', None)  # client search string
        self.search_fields = getattr(options, 'search_fields', None)  # extra searchable ORM fields
        self.unsortable_columns = getattr(options, 'unsortable_columns', None)
        self.hidden_columns = getattr(options, 'hidden_columns', None)  # generated, but hidden
        self.structure_template = getattr(options, 'structure_template', "datatableview/default_structure.html")

        self.result_counter_id = getattr(options, 'result_counter_id', 'id_count')

        # Dictionaries of column names to values
        self.labels = getattr(options, 'labels', None)
        self.processors = getattr(options, 'processors', None)


default_options = DatatableOptions()

class DatatableMetaclass(type):
    """
    Each declared Datatable object inspects its declared "fields" in order to facilitate an
    inheritance system resembling the django.forms system.  Except for our custom Meta options that
    offer field options ('labels', 'processors', etc), this code is essentially a clone of the
    django.forms strategy.
    """

    def __new__(cls, name, bases, attrs):
        declared_columns = get_declared_columns(bases, attrs, with_base_columns=False)
        new_class = super(DatatableMetaclass, cls).__new__(cls, name, bases, attrs)

        opts = new_class._meta = new_class.options_class(getattr(new_class, 'Meta', None))
        if opts.model:
            columns = columns_for_model(opts.model, opts.columns, opts.exclude, opts.labels,
                                        opts.processors, opts.unsortable_columns, opts.hidden_columns)
            none_model_columns = [k for k, v in six.iteritems(columns) if not v]
            missing_columns = set(none_model_columns) - set(declared_columns.keys())

            for name, column in declared_columns.items():
                column.name = name
                if not column.sources:
                    column.sources = [name]
                if not column.label:
                    field, _, _, _ = opts.model._meta.get_field_by_name(name)
                    column.label = pretty_name(field.verbose_name)

            columns.update(declared_columns)
        else:
            columns = declared_columns
            missing_columns = []

        new_class.declared_columns = declared_columns
        new_class.base_columns = columns
        new_class.missing_columns = missing_columns
        return new_class


@python_2_unicode_compatible
class Datatable(six.with_metaclass(DatatableMetaclass)):
    """
    Declaration container for a clientside datatable, containing an optional Meta inner class,
    class-level field declarations, and callbacks for filtering and post-processing values requested
    by the client.

    Client options sent over AJAX GET parameters will override the settings given in the inner Meta
    class.

    This object can be sent to a template context and rendered there in order to generate an
    annotated HTML frame for the javascript to initialize.
    """

    options_class = DatatableOptions

    def __init__(self, object_list, url, view=None, callback_target=None, model=None,
                 query_config=None, **kwargs):
        self.object_list = object_list
        self.url = url
        self.view = view
        self.forward_callback_target = callback_target
        self.model = model or self._meta.model
        if self.model is None and hasattr(object_list, 'model'):
            self.model = object_list.model

        self.extra_columns = kwargs.get('columns', None)
        self.columns = copy.deepcopy(self.base_columns)
        self.configure(self._meta.__dict__, kwargs, query_config)

        self.total_initial_record_count = None
        self.unpaged_record_count = None

    def configure(self, meta_config, view_config, query_config):
        """
        Combines (in order) the declared/inherited inner Meta, any view options, and finally any
        valid AJAX GET parameters from client modifications to the data they see.
        """
        # Overwriting with **view_config is safe because unspecified view-level settings do not come
        # through as None.
        declared_config = dict(meta_config, **view_config)

        # View-supplied columns should replace the ones brought by the Datatable
        if self.extra_columns is not None:
            declared_config['columns'] = self._meta.columns = self.extra_columns
            replacement_columns = columns_for_model(self.model, fields=self.extra_columns)
            self.missing_columns = set()
            for name, column in tuple(replacement_columns.items()):
                if column is None:
                    self.missing_columns.add(name)
                    replacement_columns.pop(name)
            self.columns = replacement_columns

        self.resolve_virtual_columns(*tuple(self.missing_columns))

        self.config = self.normalize_config(declared_config, query_config)

        column_order = list(self.columns.keys())
        if self.config['ordering']:
            for i, name in enumerate(self.config['ordering']):
                column_name = name.lstrip('-+')
                try:
                    index = column_order.index(column_name)
                except ValueError:
                    # It is important to ignore a bad ordering name, since the model.Meta may
                    # specify a field name that is not present on the datatable columns list.
                    continue
                self.columns[column_name].sort_priority = i
                self.columns[column_name].sort_direction = 'desc' if name[0] == '-' else 'asc'
                self.columns[column_name].index = index

    # Client request configuration mergers
    def normalize_config(self, config, query_config):
        """
        Merge the declared configuration with whatever valid query parameters are found from the
        client's AJAX request.
        """

        # Core options, not modifiable by client updates
        if config['hidden_columns'] is None:
            config['hidden_columns'] = []
        if config['search_fields'] is None:
            config['search_fields'] = []
        if config['unsortable_columns'] is None:
            config['unsortable_columns'] = []

        for option in ['search', 'start_offset', 'page_length', 'ordering']:
            normalizer_f = getattr(self, 'normalize_config_{}'.format(option))
            config[option] = normalizer_f(config, query_config)

        return config

    def normalize_config_search(self, config, query_config):
        return query_config.get(OPTION_NAME_MAP['search'], '').strip()

    def normalize_config_start_offset(self, config, query_config):
        try:
            start_offset = query_config.get(OPTION_NAME_MAP['start_offset'], 0)
            start_offset = int(start_offset)
        except ValueError:
            start_offset = 0
        else:
            if start_offset < 0:
                start_offset = 0
        return start_offset

    def normalize_config_page_length(self, config, query_config):
        try:
            page_length = query_config.get(OPTION_NAME_MAP['page_length'], config['page_length'])
            page_length = int(page_length)
        except ValueError:
            page_length = config['page_length']
        else:
            if page_length == -1:  # dataTables' way of asking for all items, no pagination
                pass
            elif page_length < MINIMUM_PAGE_LENGTH:
                page_length = MINIMUM_PAGE_LENGTH
        return page_length

    def normalize_config_ordering(self, config, query_config):
        # For "n" columns (iSortingCols), the queried values iSortCol_0..iSortCol_n are used as
        # column indices to check the values of sSortDir_X and bSortable_X

        default_ordering = config['ordering']
        ordering = []
        columns_list = list(self.columns.values())

        try:
            num_sorting_columns = int(query_config.get(OPTION_NAME_MAP['num_sorting_columns'], 0))
        except ValueError:
            num_sorting_columns = 0

        # Default sorting from view or model definition
        if num_sorting_columns == 0:
            return default_ordering

        for sort_queue_i in range(num_sorting_columns):
            try:
                column_index = int(query_config.get(OPTION_NAME_MAP['sort_column'] % sort_queue_i, ''))
            except ValueError:
                continue

            # Reject out-of-range sort requests
            if column_index >= len(columns_list):
                continue

            column = columns_list[column_index]

            # Reject requests for unsortable columns
            if column.name in config['unsortable_columns']:
                continue

            sort_direction = query_config.get(OPTION_NAME_MAP['sort_column_direction'] % sort_queue_i, None)

            sort_modifier = None
            if sort_direction == 'asc':
                sort_modifier = ''
            elif sort_direction == 'desc':
                sort_modifier = '-'
            else:
                # Aggressively skip invalid specification
                continue

            ordering.append('%s%s' % (sort_modifier, column.name))

        if not ordering and config['model']:
            return config['model']._meta.ordering
        return ordering

    def resolve_virtual_columns(self, *names):
        """
        Called with ``*args`` from the Meta.columns declaration that don't match the model's known
        fields.  This method can inspect these names and decide what to do with them in special
        scenarios, but by default, they are simply raised in an exception to notify the developer of
        an apparent configuration error.
        """
        if names:
            raise ColumnError("Unknown column name(s): %r" % (names,))

    # Reflection methods for wrapped columns
    def get_ordering_splits(self):
        """
        Returns a 2-tuple of database-sortable and non-database-sortable column names.  The first
        list ends when the first non-db column is found.  It is therefore possible that
        ``virtual_fields`` contains subsequent real db-backed fields, but because arrangement of the
        ordering fields matters, we can't respect those until manual ordering has been done on the
        intervening non-db fields.
        """
        if self.config['ordering'] is None:
            return [], []

        db_fields = []
        virtual_fields = []
        i = 0
        for i, name in enumerate(self.config['ordering']):
            column = self.columns[name]
            if column.get_db_sources():
                break
        else:
            i = len(self.config['ordering'])
        return self.config['ordering'][:i], self.config['ordering'][i:]

    def get_db_splits(self):
        """  """
        db_fields = []
        virtual_fields = []
        for name in enumerate(self.config['ordering']):
            column = self.columns[name]
            if column.get_db_sources():
                db_fields.append(name)
            else:
                virtual_fields.append(name)
        return self.config['ordering'][:i], self.config['ordering'][i:]

    # Data retrieval
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
        """
        Returns the fully processed list of records for the given set of options.

        After ensuring that the records are populated from the underlying object_list and
        configuration options, the records will finally have paging applied before the list is sent
        to the column data getters.

        Paging has been performed at this stage!
        """
        if not hasattr(self, '_records'):
            self.populate_records()

        page_data = []
        for obj in self._get_current_page():
            try:
                record_data = self.get_record_data(obj)
            except SkipRecord:
                pass
            else:
                page_data.append(record_data)
        return page_data

    def populate_records(self):
        """
        Applies the final normalized configuration on the object_list to get the final list of
        records.  Note that there is no memoization here; calling this method means work will be
        performed.

        The if ``self.object_list`` is a queryset instead of a list, the queryset will lazily avoid
        executing any queries as long as the operations requested by the configuration are call
        database-backed operations.  If they are not, the queryset will be evaluated and then
        converted to a list for clarity about what has taken place.

        No paging will take place at this stage!
        """
        self._records = None
        objects = self.object_list
        objects = self.search(objects)
        objects = self.sort(objects)
        self._records = objects

    def search(self, queryset):
        """ Performs db-only queryset searches. """
        table_queries = []
        for name, column in self.columns.items():
            # TODO: Column-specific search terms
            terms = self.config['search']
            terms = filter(None, map(lambda t: t.strip("'\" "), smart_split(terms)))

            search_f = getattr(self, 'search_%s', self._search_column)
            q = search_f(column, terms)
            if q is not None:
                table_queries.append(q)

        if table_queries:
            q = reduce(operator.or_, table_queries)
            queryset = queryset.filter(q)

        return queryset

    def _search_column(self, column, terms):
        """ Requests search queries to perform on  """
        return column.search(self.model, terms)

    def sort(self, queryset):
        """ Performs db-only queryset sorts. """
        fields = []
        db, virtual = self.get_ordering_splits()
        for name in db:
            column = self.columns[name]
            sources = column.get_sort_fields()
            if sources:
                fields.extend(sources)

        return queryset.order_by(*fields)

    # Per-record callbacks
    def preload_record_data(self, obj):
        """
        An empty hook for doing something with ``instance`` before column lookups are called
        against the object. The dict of items returned will be passed as keyword arguments to any
        of the ``get_column_FIELD_NAME_data()`` methods.
        """

        return {}

    def get_object_pk(self, obj):
        """ Returns the object's ``pk`` value. """
        return obj.pk

    def get_extra_record_data(self, obj):
        """ Returns a dictionary of JSON-friendly data sent to the client as ``"DT_RowData"``. """
        return {}

    def get_record_data(self, obj):
        """
        Returns a list of column data intended to be passed directly back to dataTables.js.

        Each column generates a 2-tuple of data. [0] is the data meant to be displayed to the client
        and [1] is the data in plain-text form, meant for manual searches.  One wouldn't want to
        include HTML in [1], for example.
        """

        preloaded_kwargs = self.preload_record_data(obj)
        data = {
            'pk': self.get_object_pk(obj),
            '_extra_data': self.get_extra_record_data(obj),
        }
        for i, (name, column) in enumerate(self.columns.items()):
            kwargs = dict(preloaded_kwargs, **{
                'datatable': self,
                'view': self.view,
                'field_name': column.name,
            })
            value = self.get_column_value(obj, column, **kwargs)
            processor = self._get_processor_method(i, column)
            if processor:
                value = processor(obj, default_value=value[0], rich_value=value[1], **kwargs)

            # A 2-tuple at this stage has presumably served its purpose in the processor callback,
            # so we convert it to its "rich" value for display purposes.
            if isinstance(value, (tuple, list)):
                value = value[1]

            if six.PY2 and isinstance(value, str):  # not unicode
                value = value.decode('utf-8')
            data[str(i)] = six.text_type(value)
        return data

    def get_column_value(self, obj, column, **kwargs):
        """ Returns whatever the column derived as the source value. """
        return column.value(obj, **kwargs)

    def _get_processor_method(self, i, column):
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

        callback = column.processor
        if callback:
            if callable(callback):
                return callback
            if self.forward_callback_target:
                f = getattr(self.forward_callback_target, callback, None)
            else:
                f = None
            if f:
                return f
            return getattr(self, callback)
                

        if self.forward_callback_target:
            f = getattr(self.forward_callback_target, 'get_column_%s_data' % (column.name,), None)
            if f:
                return f

            f = getattr(self.forward_callback_target, 'get_column_%d_data' % (i,), None)
            if f:
                return f

        f = getattr(self, 'get_column_%s_data' % (column.name,), None)
        if f:
            return f

        f = getattr(self, 'get_column_%d_data' % (i,), None)
        if f:
            return f

        return None


    # Template rendering features
    def __str__(self):
        context = {
            'url': self.url,
            'config': self.config,
            'datatable': self,
            'columns': self.columns.values(),
        }
        return render_to_string(self.config['structure_template'], context)

    def __iter__(self):
        """
        Yields a 2-tuple for each column in the form ("Column Name", " data-attribute='asdf'"),
        """

        for column in self.columns.values():
            yield column


class ValuesDatatable(Datatable):
    """
    Variant of the standard Datatable that terminates its queryset with ``.values()`` and assigns
    the results to the column values.
    """
    def populate_records(self):
        """
        Switches the object_list to a ValuesQuerySet with the given columns' ``sources`` lists.
        """
        # Figure out the full list of ORM path names
        self.column_queries = OrderedDict({'pk': 'pk'})
        for name, column in self.columns.items():
            self.column_queries.update(OrderedDict([
                (source, name) for source in column.sources
            ]))

        # Convert to a ValuesQuerySet
        self.object_list = self.object_list.values(*self.column_queries.keys())

        super(ValuesDatatable, self).populate_records()

    def get_object_pk(self, obj):
        """ Reads the pk from the ValuesQuerySet entry. """
        return obj['pk']

    def preload_record_data(self, obj):
        """
        Add entries to the object dictionary for the real column names mapped to the value from the
        source, so that it's more natural to deal with long ORM query paths.

        Example conversion:
        
            {'pk': 1, 'blog__name': "My Blog"}

        becomes:

            {'pk': 1': 'blog_name': "My Blog", 'blog': "My Blog"}

        If a column declared a plural ``sources`` list, the values at the corresponding object will
        also be a list.
        """
        data = {}

        for orm_path, column_name in self.column_queries.items():
            value = obj[orm_path]
            if column_name not in data:
                data[column_name] = value
            else:
                if not isinstance(data[column_name], (tuple, list)):
                    data[column_name] = [data[column_name]]
                data[column_name].append(value)
        obj.update(data)
        return super(ValuesDatatable, self).preload_record_data(obj)


class LegacyDatatable(Datatable):
    def resolve_virtual_columns(self, *names):
        """
        Assume that all ``names`` are legacy-style declarations and generate columns accordingly.
        """
        from .views.legacy import get_field_definition
        virtual_columns = {}
        for name in names:
            field = get_field_definition(name)
            column = columns.TextColumn(sources=field.fields, label=field.pretty_name,
                                        processor=field.callback)
            virtual_columns[name] = column

        # Make sure it's in the same order as originally defined
        new_columns = OrderedDict()
        for name in self._meta.columns:  # Can't use self.config yet, hasn't been generated
            if name in self.columns:
                new_columns[name] = self.columns[name]
            else:
                new_columns[name] = virtual_columns[name]
        self.columns = new_columns
