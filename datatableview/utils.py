from UserDict import UserDict

from django.utils.encoding import StrAndUnicode
from django.template.loader import render_to_string

# Sane boundary constants
MINIMUM_PAGE_LENGTH = 5

DEFAULT_OPTIONS = {
    'columns': [], # table headers
    'ordering': [], # override to Model._meta.ordering
    'filters': {}, # field_name__lookuptype: value
    'start_offset': 0, # results to skip ahead
    'page_length': 25, # length of a single result page
    'search': None, # client search string
    'unsortable_columns': [], # table headers not allowed to be sorted
    'structure_template': "datatableview/default_structure.html",
    
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

class DatatableStructure(StrAndUnicode):
    """
    A class designed to be echoed directly to into template HTML to represent a skeleton table
    structure that datatables.js can use.
    
    """
    
    def __init__(self, ajax_url, model, options):
        self.ajax_url = ajax_url
        self.model = model
        self.options = options
        
    def __unicode__(self):
        return render_to_string(self.options.structure_template, {
            'url': self.ajax_url,
            'column_info': self.get_column_info(),
        })
    
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
                name = name[0]
            elif name in model_fields:
                # Get the raw field name's verbose_name attribute.
                field, model, direct, m2m = self.model._meta.get_field_by_name(name)
                name = field.verbose_name.capitalize()
            # else:
            #     # Purely virtual column name
            #     name = name.capitalize()
            
            column_info.append((name, ' data-bSortable="true"'))
        
        return column_info

class DatatableOptions(UserDict):
    """
    Modifications made to the object's "self" are automatically associated with the current user
    session, making them sticky between page views.
    
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
        
        # Absorb query GET params
        kwargs = self._normalize_options(query_parameters, kwargs)
        
        UserDict.__init__(self, DEFAULT_OPTIONS, *args, **kwargs)
    
    def __getattr__(self, k):
        if k.startswith('_'):
            try:
                return self.__dict__[k]
            except KeyError:
                raise AttributeError
        try:
            return self.data[k]
        except KeyError:
            raise ValueError("%s doesn't support option %r" % (self.__class__.__name__, k))
    
    def update_from_request(self, query):
        new_options = self._normalize_options(query, self.data)
        self.update(new_options)
        
    def _normalize_options(self, query, options):
        """
        Validates incoming options in the request query parameters.
        
        """
        
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
            if page_length < MINIMUM_PAGE_LENGTH:
                page_length = MINIMUM_PAGE_LENGTH
        options['page_length'] = page_length
        
        # Ordering
        # For "n" columns (iSortingCols), the queried values iSortCol_0..iSortCol_n are used as
        # column indices to check the values of sSortDir_X and bSortable_X
        options['ordering'] = []
        try:
            num_sorting_columns = int(query.get(OPTION_NAME_MAP['num_sorting_columns'], 0))
        except ValueError:
            num_sorting_columns = 0
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
                        if len(field_name) == 2:
                            name, field_name = field_name
                        else:
                            name, field_name, data_f = field_name
                        field_name = '!{}'.format(column_index)
                    else:
                        name = field_name
                        if field_name not in self._model._meta.get_all_field_names():
                            field_name = '!{}'.format(column_index)

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
def split_real_fields(model, field_list, key=None):
    """
    Splits a list of field names on the first name that isn't in the model's concrete fields.  This
    is used repeatedly for allowing a client to request sorting or filtering on virtual or compound
    columns in the display.
    
    If ``key`` is specified, it is used to access items in ``field_list`` for the comparison.
    
    Returns a 2-tuple, where the database can safely handle the first item, and the second must be
    handled in code.
    
    """
    
    if key:
        field_list = map(key, field_list)
    concrete_names = model._meta.get_all_field_names()
    
    i = 0
    
    for i, field_name in enumerate(field_list):
        if field_name not in concrete_names:
            break
    
    return field_list[:i], field_list[i:]

def filter_real_fields(model, field_list, key=None):
    """
    Like ``split_real_fields``, except that the returned 2-tuple is [0] the set of concrete field
    names that can be queried in the ORM, and [1] the set of virtual names that can't be handled.
    
    """
    
    if key:
        field_map = dict(zip(map(key, field_list), field_list))
    else:
        field_map = dict(zip(field_list, field_list))
    
    field_list = set(field_map.keys())
    concrete_names = set(model._meta.get_all_field_names())
    
    # Do some math with sets
    concrete_fields = concrete_names.intersection(field_list)
    virtual_fields = field_list.difference(concrete_names)
    
    # Get back the original data items that correspond to the found data
    return map(field_map.get, concrete_fields), map(field_map.get, virtual_fields)
