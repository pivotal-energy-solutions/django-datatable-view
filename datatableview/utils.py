from UserDict import UserDict

from django.utils.encoding import StrAndUnicode
from django.template.loader import render_to_string
from django.db.models.fields import FieldDoesNotExist

# Sane boundary constants
MINIMUM_PAGE_LENGTH = 5

DEFAULT_OPTIONS = {
    'columns': [],  # table headers
    'ordering': [],  # override to Model._meta.ordering
    'filters': {},  # field_name__lookuptype: value
    'start_offset': 0,  # results to skip ahead
    'page_length': 25,  # length of a single result page
    'search': None,  # client search string
    'search_fields': [],  # extra ORM paths to search; not displayed
    'unsortable_columns': [],  # table headers not allowed to be sorted
    'hidden_columns': [],  # table headers to be generated, but hidden by the client
    'structure_template': "datatableview/default_structure.html",
    'result_counter_id': 'id_count',  # HTML element ID to display the total results

    # TODO: Support additional field options:
    # 'exclude': [],
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

# Private utilities
_javascript_boolean = {
    True: 'true',
    False: 'false',
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


class DatatableStructure(StrAndUnicode):
    """
    A class designed to be echoed directly to into template HTML to represent a skeleton table
    structure that datatables.js can use.

    """

    def __init__(self, ajax_url, model, options):
        self.url = ajax_url
        self.model = model
        self.options = options

        ordering = options.ordering or model._meta.ordering
        self.ordering = {}
        for i, name in enumerate(ordering):
            plain_name = name.lstrip('-+')
            index = options.get_column_index(plain_name)
            if index == -1:
                continue
            sort_direction = 'desc' if name[0] == '-' else 'asc'
            self.ordering[plain_name] = (i, index, sort_direction)

    def __unicode__(self):
        return render_to_string(self.options.structure_template, {
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

            ("column_name", ' data-bSortable="true"',)

        """

        column_info = []
        model_fields = self.model._meta.get_all_field_names()

        for name in self.options.columns:
            if isinstance(name, (tuple, list)):
                # Take the friendly representation
                name = pretty_name = name[0]
            elif name in model_fields:
                # Get the raw field name's verbose_name attribute.
                field, model, direct, m2m = self.model._meta.get_field_by_name(name)
                pretty_name = field.verbose_name.capitalize()
            else:
                # Purely virtual column name
                pretty_name = name.capitalize()

            attributes = self.get_column_attributes(name)

            attributes_string = ' '.join('{0}="{1}"'.format(*item) for item in attributes.items())
            column_info.append((pretty_name, attributes_string))

        return column_info

    def get_column_attributes(self, name):
        attributes = {
            'data-sortable': _javascript_boolean[name not in self.options.unsortable_columns],
            'data-visible': _javascript_boolean[name not in self.options.hidden_columns],
        }

        if name in self.ordering:
            attributes['data-sorting'] = ','.join(map(unicode, self.ordering[name]))

        return attributes


class DatatableOptions(UserDict):
    """
    ``columns``: An iterable of column names.  If any item is a 2-tuple, it is treated as a
    description in the form of ('Display Name', 'attribute_name'), where 'attribute_name' will be
    looked up in the following order: instance.attribute_name(), instance.attribute_name,
    view.attribute_name(instance)

    ``ordering``: A list or tuple of column names to sort by.  If empty or ``None``, the model's
    default Meta.ordering option is respected.  Names corresponding to a database-backed field can
    be dealt with in the database, but virtual columns that exist as compound data cells need to be
    handled in code, which has a hard efficiency limit.  Mixing real and virtual columns tries to
    be as efficient as possible by letting the database do the sorting first, but ultimately
    triggers the code-driven ordering.

    """

    def __init__(self, model, query_parameters, *args, **kwargs):
        self._model = model

        # Core options, not modifiable by client updates
        if 'columns' not in kwargs:
            model_fields = model._meta.local_fields
            kwargs['columns'] = map(lambda f: f.verbose_name.capitalize(), model_fields)

        if 'hidden_columns' not in kwargs or kwargs['hidden_columns'] is None:
            kwargs['hidden_columns'] = []

        if 'search_fields' not in kwargs or kwargs['search_fields'] is None:
            kwargs['search_fields'] = []

        # Absorb query GET params
        kwargs = self._normalize_options(query_parameters, kwargs)

        UserDict.__init__(self, DEFAULT_OPTIONS, *args, **kwargs)

        self._flat_column_names = []
        for field_name in self.columns:
            if isinstance(field_name, (tuple, list)):
                pretty_name, field_name = field_name[:2]

            if not field_name or isinstance(field_name, (tuple, list)):
                field_name = pretty_name

            self._flat_column_names.append(field_name)

    def __getattr__(self, k):
        try:
            return self.data[k]
        except KeyError:
            raise AttributeError("%s doesn't support option %r" % (self.__class__.__name__, k))

    def _normalize_options(self, query, options):
        """ Validates incoming options in the request query parameters. """

        # Search
        options['search'] = query.get(OPTION_NAME_MAP['search'], '').strip()

        # Page start offset
        try:
            start_offset = query.get(OPTION_NAME_MAP['start_offset'], DEFAULT_OPTIONS['start_offset'])
            start_offset = int(start_offset)
        except ValueError:
            start_offset = DEFAULT_OPTIONS['start_offset']
        else:
            if start_offset < 0:
                start_offset = 0
        options['start_offset'] = start_offset

        # Page length
        try:
            page_length = query.get(OPTION_NAME_MAP['page_length'], DEFAULT_OPTIONS['page_length'])
            page_length = int(page_length)
        except ValueError:
            page_length = DEFAULT_OPTIONS['page_length']
        else:
            if page_length == -1:  # datatable's way of asking for all items, no pagination
                pass
            elif page_length < MINIMUM_PAGE_LENGTH:
                page_length = MINIMUM_PAGE_LENGTH
        options['page_length'] = page_length

        # Ordering
        # For "n" columns (iSortingCols), the queried values iSortCol_0..iSortCol_n are used as
        # column indices to check the values of sSortDir_X and bSortable_X
        default_ordering = options.get('ordering')
        options['ordering'] = []
        try:
            num_sorting_columns = int(query.get(OPTION_NAME_MAP['num_sorting_columns'], 0))
        except ValueError:
            num_sorting_columns = 0

        # Default sorting from view or model definition
        if not num_sorting_columns:
            options['ordering'] = default_ordering
        else:
            for sort_queue_i in range(num_sorting_columns):
                try:
                    column_index = int(query.get(OPTION_NAME_MAP['sort_column'] % sort_queue_i, ''))
                except ValueError:
                    continue
                else:
                    # Reject out-of-range sort requests
                    if column_index >= len(options['columns']):
                        continue

                    field_name = options['columns'][column_index]
                    if isinstance(field_name, (tuple, list)):
                        name, field_name = field_name[:2]

                        # If the database source for the field is None, then this column will be
                        # forcefully sorted in code.  If the field_name is an iterable of compound
                        # sources, the final output from the data method should also be used.
                        if not field_name or isinstance(field_name, (tuple, list)):
                            field_name = '!{0}'.format(column_index)
                    else:
                        name = field_name

                        # If the singular column name isn't a model field, mark it for manual handling
                        if field_name not in self._model._meta.get_all_field_names():
                            field_name = '!{0}'.format(column_index)

                    # Reject requests for unsortable columns
                    if name in options.get('unsortable_columns', []):
                        continue

                    # Get the client's requested sort direction
                    sort_direction = query.get(OPTION_NAME_MAP['sort_column_direction'] % sort_queue_i, None)

                    sort_modifier = None
                    if sort_direction == 'asc':
                        sort_modifier = ''
                    elif sort_direction == 'desc':
                        sort_modifier = '-'
                    else:
                        continue

                    options['ordering'].append('%s%s' % (sort_modifier, field_name))

        return options

    def get_column_index(self, name):
        if name.startswith('!'):
            return int(name[1:])
        try:
            return self._flat_column_names.index(name)
        except ValueError:
            return -1


def get_datatable_structure(ajax_url, model, options):
    """
    Uses ``options``, a dict or DatatableOptions, into a ``DatatableStructure`` for template use.

    """

    if not isinstance(options, DatatableOptions):
        options = DatatableOptions(model, {}, **options)

    return DatatableStructure(ajax_url, model, options)


def split_real_fields(model, field_list, key=None):
    """
    Splits a list of field names on the first name that isn't in the model's concrete fields.  This
    is used repeatedly for allowing a client to request sorting or filtering on virtual or compound
    columns in the display.

    If ``key`` is specified, it is used to access items in ``field_list`` for the comparison, in
    the same fashion as the built-in ``sort`` function.

    Returns a 2-tuple, where the database can safely handle the first item, and the second must be
    handled in code.

    """

    if key:
        field_list = map(key, field_list)

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

    field_map = dict(zip(map(key, fields), fields))

    field_list = set(field_map.keys())
    concrete_names = set(model._meta.get_all_field_names())

    # Do some math with sets
    concrete_fields = concrete_names.intersection(field_list)
    virtual_fields = field_list.difference(concrete_names)

    # Get back the original data items that correspond to the found data
    db_fields = filter(lambda f: (key(f) if key else f) in concrete_fields, fields)
    virtual_fields = map(field_map.get, virtual_fields)
    return db_fields, virtual_fields
