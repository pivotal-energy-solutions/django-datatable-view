from collections import namedtuple
import operator
try:
    from functools import reduce
except ImportError:
    pass
try:
    from collections import UserDict
except ImportError:
    from UserDict import UserDict

from django import get_version
from django.db import models
from django.db.models import Manager, Q
from django.db.models.fields import FieldDoesNotExist
from django.template.loader import render_to_string
from django.forms.util import flatatt
from django.utils.text import smart_split
try:
    from django.utils.encoding import python_2_unicode_compatible
except ImportError:
    from .compat import python_2_unicode_compatible

import dateutil.parser
import six

# Sane boundary constants
MINIMUM_PAGE_LENGTH = 5

DEFAULT_OPTIONS = {
    'columns': [],  # table headers
    'ordering': [],  # override to Model._meta.ordering
    'start_offset': 0,  # results to skip ahead
    'page_length': 25,  # length of a single result page
    'search': '',  # client search string
    'search_fields': [],  # extra ORM paths to search; not displayed
    'unsortable_columns': [],  # table headers not allowed to be sorted
    'hidden_columns': [],  # table headers to be generated, but hidden by the client
    'structure_template': "datatableview/default_structure.html",
    'result_counter_id': 'id_count',  # HTML element ID to display the total results
}

# Since it's rather painful to deal with the datatables.js naming scheme in Python, this map changes
# the Pythonic names to the javascript ones in the GET request
OPTION_NAME_MAP = {
    'start_offset': 'iDisplayStart',
    'page_length': 'iDisplayLength',
    'search': 'sSearch',
    'num_sorting_columns': 'iSortingCols',
    'sort_column': 'iSortCol_%d',
    'sort_column_direction': 'sSortDir_%d',
}

# Mapping of Django field categories to the set of field classes falling into that category.
# This is used during field searches to know which ORM language queries can be applied to a field,
# such as "__icontains" or "__year".
FIELD_TYPES = {
    'text': [models.CharField, models.TextField, models.FileField],
    'date': [models.DateField],
    'boolean': [models.BooleanField, models.NullBooleanField],
    'integer': [models.IntegerField, models.AutoField],
    'float': [models.FloatField, models.DecimalField],

    # This is a special type for fields that should be passed up, since there is no intuitive
    # meaning for searches done agains the FK field directly.
    'ignored': [models.ForeignKey],
}
if hasattr(models, 'GenericIPAddressField'):
    FIELD_TYPES['text'].append(models.GenericIPAddressField)

# Mapping of Django's supported field types to their more generic type names.
# These values are primarily used for the xeditable field type lookups.
# TODO: Would be nice if we can derive these from FIELD_TYPES so there's less repetition.
XEDITABLE_FIELD_TYPES = {
    'AutoField': 'number',
    'BooleanField': 'text',
    'CharField': 'text',
    'CommaSeparatedIntegerField': 'text',
    'DateField': 'date',
    'DateTimeField': 'datetime',
    'DecimalField': 'text',
    'FileField': 'text',
    'FilePathField': 'text',
    'FloatField': 'number',
    'IntegerField': 'number',
    'BigIntegerField': 'number',
    'IPAddressField': 'text',
    'GenericIPAddressField': 'text',
    'NullBooleanField': 'text',
    'PositiveIntegerField': 'number',
    'PositiveSmallIntegerField': 'number',
    'SlugField': 'text',
    'SmallIntegerField': 'number',
    'TextField': 'text',
    'TimeField': 'text',
}

# Private utilities
_javascript_boolean = {
    True: 'true',
    False: 'false',
}
FieldDefinitionTuple = namedtuple('FieldDefinitionTuple', ['pretty_name', 'fields', 'callback'])
ColumnOrderingTuple = namedtuple('ColumnOrderingTuple', ['order', 'column_index', 'direction'])
ColumnInfoTuple = namedtuple('ColumnInfoTuple', ['pretty_name', 'attrs'])

def resolve_orm_path(model, orm_path):
    """
    Follows the queryset-style query path of ``orm_path`` starting from ``model`` class.  If the
    path ends up referring to a bad field name, ``django.db.models.fields.FieldDoesNotExist`` will
    be raised.

    """

    bits = orm_path.split('__')
    endpoint_model = reduce(get_model_at_related_field, [model] + bits[:-1])
    field, _, _, _ = endpoint_model._meta.get_field_by_name(bits[-1])
    return field


def get_model_at_related_field(model, attr):
    """
    Looks up ``attr`` as a field of ``model`` and returns the related model class.  If ``attr`` is
    not a relationship field, ``ValueError`` is raised.

    """

    try:
        field, _, direct, m2m = model._meta.get_field_by_name(attr)
    except FieldDoesNotExist:
        raise

    if not direct and hasattr(field, 'model'):  # Reverse relationship
        model = field.model
    elif hasattr(field, 'rel') and field.rel:  # Forward/m2m relationship
        model = field.rel.to
    else:
        raise ValueError("{0}.{1} ({2}) is not a relationship field.".format(model.__name__, attr,
                field.__class__.__name__))
    return model


def get_first_orm_bit(field_definition):
    """ Returns the first ORM path component of a field definition's declared db field. """
    column = get_field_definition(field_definition)

    if not column.fields:
        return None

    return column.fields[0].split('__')[0]


def get_field_definition(field_definition):
    """ Normalizes a field definition into its component parts, even if some are missing. """
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


def normalize_config(config, query_config, model=None):
    # Search
    config['search'] = query_config.get(OPTION_NAME_MAP['search'], '').strip()

    # Page start offset
    try:
        start_offset = query_config.get(OPTION_NAME_MAP['start_offset'], 0)
        start_offset = int(start_offset)
    except ValueError:
        start_offset = 0
    else:
        if start_offset < 0:
            start_offset = 0
    config['start_offset'] = start_offset

    # Page length
    try:
        page_length = query_config.get(OPTION_NAME_MAP['page_length'], config['page_length'])
        page_length = int(page_length)
    except ValueError:
        page_length = config['page_length']
    else:
        if page_length == -1:  # datatable's way of asking for all items, no pagination
            pass
        elif page_length < MINIMUM_PAGE_LENGTH:
            page_length = MINIMUM_PAGE_LENGTH
    config['page_length'] = page_length

    # Ordering
    # For "n" columns (iSortingCols), the queried values iSortCol_0..iSortCol_n are used as
    # column indices to check the values of sSortDir_X and bSortable_X
    default_ordering = config.get('ordering')
    config['ordering'] = []
    try:
        num_sorting_columns = int(query_config.get(OPTION_NAME_MAP['num_sorting_columns'], 0))
    except ValueError:
        num_sorting_columns = 0

    # Default sorting from view or model definition
    if not num_sorting_columns:
        config['ordering'] = default_ordering
    else:
        for sort_queue_i in range(num_sorting_columns):
            try:
                column_index = int(query_config.get(OPTION_NAME_MAP['sort_column'] % sort_queue_i, ''))
            except ValueError:
                continue
            else:
                # Reject out-of-range sort requests
                if column_index >= len(config['columns']):
                    continue

                column = config['columns'][column_index]
                column = get_field_definition(column)
                is_local_field = False
                if column.fields:
                    base_field_name = column.fields[0].split('__')[0]
                    if base_field_name in model._meta.get_all_field_names():
                        is_local_field = True

                if not column.fields or len(column.fields) > 1 or not is_local_field:
                    field_name = '!{0}'.format(column_index)

                if is_local_field:
                    name = column.fields[0]
                    field_name = name
                else:
                    name = column.pretty_name

                # Reject requests for unsortable columns
                if config['unsortable_columns'] and name in config['unsortable_columns']:
                    continue

                # Get the client's requested sort direction
                sort_direction = query_config.get(OPTION_NAME_MAP['sort_column_direction'] % sort_queue_i, None)

                sort_modifier = None
                if sort_direction == 'asc':
                    sort_modifier = ''
                elif sort_direction == 'desc':
                    sort_modifier = '-'
                else:
                    continue

                config['ordering'].append('%s%s' % (sort_modifier, field_name))
    if not config['ordering'] and model:
        config['ordering'] = model._meta.ordering

    return config

def apply_options(object_list, spec):
    """
    Interprets the datatable options.

    Options requiring manual massaging of the queryset are handled here.  The output of this
    method should be treated as a list, since complex options might convert it out of the
    original queryset form.

    """

    config = spec.config

    # These will hold residue queries that cannot be handled in at the database level.  Anything
    # in these variables by the end will be handled manually (read: less efficiently)
    sort_fields = []
    searches = []

    # This count is for the benefit of the frontend datatables.js
    total_initial_record_count = len(object_list)

    if config['ordering']:
        db_fields, sort_fields = split_real_fields(spec.model, config['ordering'])
        object_list = object_list.order_by(*db_fields)

    if config['search']:
        db_fields, searches = filter_real_fields(spec.model, config['columns'],
                                                 key=get_first_orm_bit)
        db_fields.extend(config['search_fields'])

        queries = []  # Queries generated to search all fields for all terms
        search_terms = map(lambda q: q.strip("'\" "), smart_split(config['search']))

        for term in search_terms:
            term_queries = []  # Queries generated to search all fields for this term
            # Every concrete database lookup string in 'columns' is followed to its trailing field descriptor.  For example, "subdivision__name" terminates in a CharField.  The field type determines how it is probed for search.
            for column in db_fields:
                column = get_field_definition(column)
                for component_name in column.fields:
                    field_queries = []  # Queries generated to search this database field for the search term

                    field = resolve_orm_path(spec.model, component_name)
                    if isinstance(field, tuple(FIELD_TYPES['text'])):
                        field_queries = [{component_name + '__icontains': term}]
                    elif isinstance(field, tuple(FIELD_TYPES['date'])):
                        try:
                            date_obj = dateutil.parser.parse(term)
                        except ValueError:
                            # This exception is theoretical, but it doesn't seem to raise.
                            pass
                        except TypeError:
                            # Failed conversions can lead to the parser adding ints to None.
                            pass
                        else:
                            field_queries.append({component_name: date_obj})

                        # Add queries for more granular date field lookups
                        try:
                            numerical_value = int(term)
                        except ValueError:
                            pass
                        else:
                            if 0 < numerical_value < 3000:
                                field_queries.append({component_name + '__year': numerical_value})
                            if 0 < numerical_value <= 12:
                                field_queries.append({component_name + '__month': numerical_value})
                            if 0 < numerical_value <= 31:
                                field_queries.append({component_name + '__day': numerical_value})
                    elif isinstance(field, tuple(FIELD_TYPES['boolean'])):
                        if term.lower() in ('true', 'yes'):
                            term = True
                        elif term.lower() in ('false', 'no'):
                            term = False
                        else:
                            continue

                        field_queries = [{component_name: term}]
                    elif isinstance(field, tuple(FIELD_TYPES['integer'])):
                        try:
                            field_queries = [{component_name: int(term)}]
                        except ValueError:
                            pass
                    elif isinstance(field, tuple(FIELD_TYPES['float'])):
                        try:
                            field_queries = [{component_name: float(term)}]
                        except ValueError:
                            pass
                    elif isinstance(field, tuple(FIELD_TYPES['ignored'])):
                        pass
                    else:
                        raise ValueError("Unhandled field type for %s (%r) in search." % (component_name, type(field)))

                    # Append each field inspection for this term
                    term_queries.extend(map(lambda q: Q(**q), field_queries))
            # Append the logical OR of all field inspections for this term
            if len(term_queries):
                queries.append(reduce(operator.or_, term_queries))
        # Apply the logical AND of all term inspections
        if len(queries):
            object_list = object_list.filter(reduce(operator.and_, queries))

    # TODO: Remove "and not searches" from this conditional, since manual searches won't be done
    if not sort_fields and not searches:
        # We can shortcut and speed up the process if all operations are database-backed.
        object_list = object_list
        if config['search']:
            spec.unpaged_record_count = object_list.count()
        else:
            spec.unpaged_record_count = total_initial_record_count
    else:
        object_list = ObjectListResult(object_list)

        # # Manual searches
        # # This is broken until it searches all items in object_list previous to the database
        # # sort. That represents a runtime load that hits every row in code, rather than in the
        # # database. If enabled, this would cripple performance on large datasets.
        # if config['i_walk_the_dangerous_line_between_genius_and_insanity']:
        #     length = len(object_list)
        #     for i, obj in enumerate(reversed(object_list)):
        #         keep = False
        #         for column_info in searches:
        #             column_index = config['columns'].index(column_info)
        #             rich_data, plain_data = spec.get_column_data(column_index, column_info, obj)
        #             for term in search_terms:
        #                 if term.lower() in plain_data.lower():
        #                     keep = True
        #                     break
        #             if keep:
        #                 break
        #
        #         if not keep:
        #             removed = object_list.pop(length - 1 - i)
        #             # print column_info
        #             # print data
        #             # print '===='

        # Sort the results manually for whatever remaining sort config are left over
        def data_getter_orm(field_name):
            def key(obj):
                try:
                    return reduce(getattr, [obj] + field_name.split('__'))
                except (AttributeError, ObjectDoesNotExist):
                    return None
            return key

        def data_getter_custom(i):
            def key(obj):
                rich_value, plain_value = spec.get_column_data(i, config['columns'][i], obj)
                return plain_value
            return key

        # Sort the list using the manual sort fields, back-to-front.  `sort` is a stable
        # operation, meaning that multiple passes can be made on the list using different
        # criteria.  The only catch is that the passes must be made in reverse order so that
        # the "first" sort field with the most priority ends up getting applied last.
        for sort_field in sort_fields[::-1]:
            if sort_field.startswith('-'):
                reverse = True
                sort_field = sort_field[1:]
            else:
                reverse = False

            if sort_field.startswith('!'):
                key_function = data_getter_custom
                sort_field = int(sort_field[1:])
            else:
                key_function = data_getter_orm

            try:
                object_list.sort(key=key_function(sort_field), reverse=reverse)
            except TypeError as err:
                log.error("Unable to sort on {0} - {1}".format(sort_field, err))

        spec.unpaged_record_count = len(object_list)

    spec.total_initial_record_count = total_initial_record_count
    return object_list

@python_2_unicode_compatible
class DatatableStructure(object):
    """
    A class designed to be echoed directly to into template HTML to represent a skeleton table
    structure that datatables.js can use.

    """

    def __init__(self, ajax_url, options, model=None):
        self.url = ajax_url
        self.options = options
        self.model = model

        self.ordering = {}
        if options['ordering']:
            for i, name in enumerate(options['ordering']):
                plain_name = name.lstrip('-+')
                index = options.get_column_index(plain_name)
                if index == -1:
                    continue
                sort_direction = 'desc' if name[0] == '-' else 'asc'
                self.ordering[plain_name] = ColumnOrderingTuple(i, index, sort_direction)

    def __str__(self):
        return render_to_string(self.options['structure_template'], {
            'url': self.url,
            'result_counter_id': self.options['result_counter_id'],
            'column_info': self.get_column_info(),
        })

    def __iter__(self):
        """
        Yields the column information suitable for rendering HTML.

        Each time is returned as a 2-tuple in the form ("Column Name", "data-attribute='asdf'"),

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

        for column in self.options['columns']:
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
        attributes = {
            'data-sortable': _javascript_boolean[name not in self.options['unsortable_columns']],
            'data-visible': _javascript_boolean[name not in self.options['hidden_columns']],
        }

        if name in self.ordering:
            attributes['data-sorting'] = ','.join(map(six.text_type, self.ordering[name]))

        return attributes


class DatatableOptions(UserDict):
    """ Normalizes all options to values that are guaranteed safe. """

    def __init__(self, model, query_parameters, *args, **kwargs):
        self._model = model

        # Core options, not modifiable by client updates
        if 'columns' not in kwargs:
            model_fields = model._meta.local_fields
            kwargs['columns'] = list(map(lambda f: (six.text_type(f.verbose_name), f.name), model_fields))

        if 'hidden_columns' not in kwargs or kwargs['hidden_columns'] is None:
            kwargs['hidden_columns'] = []

        if 'search_fields' not in kwargs or kwargs['search_fields'] is None:
            kwargs['search_fields'] = []

        if 'unsortable_columns' not in kwargs or kwargs['unsortable_columns'] is None:
            kwargs['unsortable_columns'] = []

        # Absorb query GET params
        kwargs = self._normalize_options(query_parameters, kwargs)

        UserDict.__init__(self, DEFAULT_OPTIONS, *args, **kwargs)

        self._flat_column_names = []
        for column in self['columns']:
            column = get_field_definition(column)
            flat_name = column.pretty_name
            if column.fields:
                flat_name = column.fields[0]
            self._flat_column_names.append(flat_name)

    def _normalize_options(self, query, options):
        """ Validates incoming options in the request query parameters. """
        return normalize_config(options, query, model=self._model)

    def get_column_index(self, name):
        if name.startswith('!'):
            return int(name[1:])
        try:
            return self._flat_column_names.index(name)
        except ValueError:
            return -1


class ObjectListResult(list):
    _dtv_total_initial_record_count = None
    _dtv_unpaged_total = None


def get_datatable_structure(ajax_url, options, model=None):
    """
    Uses ``options``, a dict or DatatableOptions, into a ``DatatableStructure`` for template use.

    """

    if not isinstance(options, DatatableOptions):
        options = DatatableOptions(model, {}, **options)

    return DatatableStructure(ajax_url, options, model=model)


def split_real_fields(model, field_list):
    """
    Splits a list of field names on the first name that isn't in the model's concrete fields.  This
    is used repeatedly for allowing a client to request sorting or filtering on virtual or compound
    columns in the display.

    Returns a 2-tuple, where the database can safely handle the first item, and the second must be
    handled in code.

    """

    i = 0

    for i, field_name in enumerate(field_list):
        if field_name[0] in '-+':
            field_name = field_name[1:]

        # Try to fetch the leaf attribute.  If this fails, the attribute is not database-backed and
        # the search for the first non-database field should end.
        try:
            resolve_orm_path(model, field_name)
        except FieldDoesNotExist:
            break
    else:
        i = len(field_list)

    return field_list[:i], field_list[i:]


def filter_real_fields(model, fields, key=None):
    """
    Like ``split_real_fields``, except that the returned 2-tuple is [0] the set of concrete field
    names that can be queried in the ORM, and [1] the set of virtual names that can't be handled.

    """

    field_hints = tuple(zip(map(key, fields), fields))
    field_map = dict(field_hints)
    field_list = set(field_map.keys())
    concrete_names = set(model._meta.get_all_field_names())

    # Do some math with sets
    concrete_fields = concrete_names.intersection(field_list)
    virtual_fields = field_list.difference(concrete_names)

    # Get back the original data items that correspond to the found data
    db_fields = []
    virtual_fields = []
    for bit, field in field_hints:
        if bit in concrete_fields:
            db_fields.append(field)
        else:
            virtual_fields.append(field)
    return db_fields, virtual_fields

