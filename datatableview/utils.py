from collections import defaultdict
import operator
try:
    from functools import reduce
except ImportError:
    pass

from django.db import models
from django.db.models import Q
from django.db.models.fields import FieldDoesNotExist
from django.core.exceptions import ObjectDoesNotExist
from django.utils.text import smart_split

import dateutil.parser

MINIMUM_PAGE_LENGTH = 1
DEFAULT_PAGE_LENGTH = 25  # legacy only
DEFAULT_EMPTY_VALUE = ""
DEFAULT_MULTIPLE_SEPARATOR = u" "

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
    'ForeignKey': 'select',
}

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


def get_first_orm_bit(column):
    """ Returns the first ORM path component of a field definition's declared db field. """
    if not column.sources:
        return None

    return column.sources[0].split('__')[0]


def apply_options(object_list, spec):
    """
    Interprets the datatable options.

    Options requiring manual massaging of the queryset are handled here.  The output of this
    method should be treated as a list, since complex options might convert it out of the
    original queryset form.

    """

    from .views.legacy import get_field_definition
    config = spec.config

    # These will hold residue queries that cannot be handled in at the database level.  Anything
    # in these variables by the end will be handled manually (read: less efficiently)
    virtual_ordering = []
    virtual_searches = []

    # This count is for the benefit of the frontend datatables.js
    total_initial_record_count = len(object_list)

    if config['ordering']:
        db_ordering, virtual_ordering = spec.get_ordering_splits()
        object_list = object_list.order_by(*db_ordering)

        # Save virtual_ordering for later

    if config['search']:
        db_searches, virtual_searches = spec.get_db_splits()
        db_searches.extend(config['search_fields'])

        queries = []  # Queries generated to search all fields for all terms
        search_terms = map(lambda q: q.strip("'\" "), smart_split(config['search']))

        for term in search_terms:
            term_queries = []  # Queries generated to search all fields for this term
            # Every concrete database lookup string in 'columns' is followed to its trailing field descriptor.  For example, "subdivision__name" terminates in a CharField.  The field type determines how it is probed for search.
            for column in db_searches:
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
    if not virtual_ordering and not virtual_searches:
        # We can shortcut and speed up the process if all operations are database-backed.
        object_list = object_list
        if config['search']:
            spec.unpaged_record_count = object_list.count()
        else:
            spec.unpaged_record_count = total_initial_record_count
    else:
        object_list = list(object_list)

        # # Manual searches
        # # This is broken until it searches all items in object_list previous to the database
        # # sort. That represents a runtime load that hits every row in code, rather than in the
        # # database. If enabled, this would cripple performance on large datasets.
        # if config['i_walk_the_dangerous_line_between_genius_and_insanity']:
        #     length = len(object_list)
        #     for i, obj in enumerate(reversed(object_list)):
        #         keep = False
        #         for column_info in virtual_searches:
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
                rich_value, plain_value = spec.get_column_data(i, spec.columns.values()[i], obj)
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


# Legacy only
def get_datatable_structure(ajax_url, options, model=None):
    """
    Uses ``options``, a dict or DatatableOptions, into a ``DatatableStructure`` for template use.
    """
    from .views.legacy import DatatableOptions, DatatableStructure
    if not isinstance(options, DatatableOptions):
        options = DatatableOptions(model, {}, **options)

    return DatatableStructure(ajax_url, options, model=model)
