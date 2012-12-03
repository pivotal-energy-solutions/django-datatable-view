import json
import re
import operator

from django.views.generic.list import ListView, MultipleObjectMixin
from django.http import HttpResponse
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models import Model, Manager, Q
from django.utils.cache import add_never_cache_headers
import dateutil.parser

from datatableview.utils import DatatableStructure, DatatableOptions, split_real_fields, \
        filter_real_fields

class DatatableMixin(MultipleObjectMixin):
    """
    Converts a view into an AJAX interface for obtaining records.
    
    The normal GET execution adds a ``DataTable`` object to the context which can be used to
    streamline the dumping of the HTML skeleton required for datatables.js to hook.  A ``DataTable``
    object doesn't hold any data, just a structure superficially generated from the options on the
    view.
    
    The template is responsible for making the AJAX request back to this view to populate the table
    with data.
    
    """
    
    datatable_options = None
    datatable_context_name = 'datatable'
    
    def get(self, request, *args, **kwargs):
        """
        Detects AJAX access and returns appropriate serialized data.  Normal access to the view is
        unmodified.
        
        """
        
        if request.is_ajax() or request.GET.get('ajax') == 'true':
            return self.get_ajax(request, *args, **kwargs)
        return super(DatatableMixin, self).get(request, *args, **kwargs)
    
    def get_object_list(self):
        """ Gets the core queryset, but applies the datatable options to it. """
        return self.apply_queryset_options(self.get_queryset())
        
    def get_datatable_options(self):
        """ Returns the DatatableOptions object for this view's configuration. """
        if not hasattr(self, '_datatable_options'):
            if not self.datatable_options:
                # No options defined on the view
                if self.model is None:
                    # Unfortunately, asking for the queryset for model class extraction might have
                    # enormous performance implications, so we raise the error.
                    raise ImproperlyConfigured("%s must declare 'model' class." % (
                            self.__class__.__name__,))
                options = DatatableOptions(self.model, self.request.GET)
            elif isinstance(self.datatable_options, DatatableOptions):
                # Options are defined, already in DatatableOptions instance
                options = self.datatable_options
            else:
                # Options are defined, but probably in a raw dict format
                if self.model is None:
                    # Unfortunately, asking for the queryset for model class extraction might have
                    # enormous performance implications, so we raise the error.
                    raise ImproperlyConfigured("%s must declare 'model' class." % (
                            self.__class__.__name__,))
                options = DatatableOptions(self.model, self.request.GET, **dict(self.datatable_options))
            
            self._datatable_options = options
        
        return self._datatable_options
    
    def apply_queryset_options(self, queryset):
        """
        Interprets the datatable options.
        
        Options requiring manual massaging of the queryset are handled here.  The output of this
        method should be treated as a list, since complex options might convert it out of the
        original queryset form.
        
        """
        
        options = self.get_datatable_options()
        
        # These will hold residue queries that cannot be handled in at the database level.  Anything
        # in these variables by the end will be handled manually (read: less efficiently)
        sort_fields = []
        # filters = []
        searches = []
        
        # This count is for the benefit of the frontend datatables.js
        total_initial_record_count = queryset.count()
        
        if options.ordering:
            db_fields, sort_fields = split_real_fields(self.model, options.ordering)
            queryset = queryset.order_by(*db_fields)
        
        # if options.filters:
        #     if isinstance(options.filters, dict):
        #         filters = options.filters.items()
        #     else:
        #         # sequence of 2-tuples
        #         filters = options.filters
        #     
        #     # The first field in a string like "description__icontains" determines if the lookup
        #     # is concrete (can be handled by the database query) or virtual.  A query such as
        #     # "foreignkey__virtualfield__icontains" is not supported.  A query such as
        #     # "virtualfield__icontains" IS supported but will be handled manually.
        #     key_function = lambda item: item[0].split('__')[0]
        #     
        #     db_filters, filters = filter_real_fields(self.model, filters, key=key_function)
        #     
        #     queryset = queryset.filter(**dict(db_filters))
        # 
        if options.search:
            def key_function(item):
                """
                Converts items in the 'columns' definition to field names for determining if it's
                concrete or not.
                
                """
                if isinstance(item, (tuple, list)):
                    item = item[1]
                    if item is None:
                        return item
                    if not isinstance(item, (tuple, list)):
                        item = (item,)
                    return item[0].split('__')[0]
                return item
            db_fields, searches = filter_real_fields(self.model, options.columns, key=key_function)
            
            queries = [] # Queries generated to search all fields for all terms
            search_terms = map(unicode.strip, options.search.split())
            
            for term in search_terms:
                term_queries = [] # Queries generated to search all fields for this term
                # Every concrete database lookup string in 'columns' is followed to its trailing field descriptor.  For example, "subdivision__name" terminates in a CharField.  The field type determines how it is probed for search.
                for name in db_fields:
                    if isinstance(name, (tuple, list)):
                        name = name[1]
                    if not isinstance(name, (tuple, list)):
                        name = (name,)
                        
                    for component_name in name:
                        field_queries = [] # Queries generated to search this database field for the search term
                        bits = component_name.split('__')
                        obj = reduce(getattr, [self.model] + bits[:-1])
                        
                        if obj is not self.model:
                            obj = obj.field.rel.to
                            
                        # Get the Field type from the related model
                        try:
                            field, model, direct, m2m = obj._meta.get_field_by_name(bits[-1])
                        except models.fields.FieldDoesNotExist:
                            # Virtual columns won't be found on the model, so this is the escape hatch
                            continue
                            
                        if isinstance(field, models.CharField):
                            field_queries = [{component_name + '__icontains': term}]
                        elif isinstance(field, (models.DateTimeField, models.DateField)):
                            try:
                                date_obj = dateutil.parser.parse(term)
                            except ValueError:
                                # This exception is theoretical, but it doesn't seem to raise.
                                pass
                            else:
                                field_queries.append({component_name: date_obj})
                            try:
                                numerical_value = int(term)
                            except ValueError:
                                pass
                            else:
                                field_queries.extend([
                                    {component_name + '__year': numerical_value},
                                    {component_name + '__month': numerical_value},
                                    {component_name + '__day': numerical_value},
                                ])
                        else:
                            raise ValueError("Unhandled field type for %s (%r) in search." % (name, type(field)))
                            
                        # print field_queries
                        
                        # Append each field inspection for this term
                        term_queries.extend(map(lambda q: Q(**q), field_queries))
                # Append the logical OR of all field inspections for this term
                queries.append(reduce(operator.or_, term_queries))
            # Apply the logical AND of all term inspections
            queryset = queryset.filter(reduce(operator.and_, queries))
        
        # Get ready to turn the results into a normal iterable, which might happen during any of the
        # following operations.
        object_list = list(queryset)
        
        # Sort the results manually for whatever remaining sort options are left over
        def data_getter_orm(field_name):
            def key(obj):
                return reduce(getattr, [obj] + field_name.split('__'))
            return key
        def data_getter_custom(i):
            def key(obj):
                rich_value, plain_value = self.get_column_data(i, options.columns[i], obj)
                return plain_value
            return key

        for sort_field in sort_fields:
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
            
            object_list = sorted(object_list, key=key_function(sort_field), reverse=reverse)
        
        # This is broken until it searches all items in object_list previous to the database sort.
        # That represents a runtime load that hits every row in code, rather than in the database.
        # If enabled, this would cripple performance on large datasets.
        # # Manual searches
        # for i, obj in enumerate(object_list[::]):
        #     keep = False
        #     for column_info in searches:
        #         for term in search_terms:
        #             column_index = options.columns.index(column_info)
        #             rich_data, plain_data = self.get_column_data(column_index, column_info, obj)
        #             if term in plain_data:
        #                 keep = True
        #                 break
        #         if keep:
        #             break
        #     
        #     if not keep:
        #         object_list.pop(i)
        #         # print column_info
        #         # print data
        #         # print '===='
        
        unpaged_total = len(object_list)
        
        # TODO: This shouldn't take place unless all sorting is done.
        object_list = object_list[options.start_offset : options.start_offset+options.page_length]
        
        return object_list, total_initial_record_count, unpaged_total
    
    def get_datatable_context_name(self):
        return self.datatable_context_name
            
    def get_datatable(self):
        """
        Returns the helper object that can be used in the template to render the datatable skeleton.
        
        """
        
        return DatatableStructure(self.request.path, self.model, self.get_datatable_options())
    
    def get_context_data(self, **kwargs):
        context = super(DatatableMixin, self).get_context_data(**kwargs)
        
        context[self.get_datatable_context_name()] = self.get_datatable()
        
        return context
    
    
    # Ajax execution methods
    def get_ajax(self, request, *args, **kwargs):
        """
        Called in place of normal ``get()`` when accessed via AJAX.
        
        """
        
        object_list = self.get_object_list()
        response = HttpResponse(self.serialize_to_json(object_list), mimetype="application/json")
        
        add_never_cache_headers(response)
        
        return response
    
    def serialize_to_json(self, object_list):
        """
        Returns the JSON string object required for dataTables.js to do its job.
        
        The value names are in the form "s~" for strings, "i~" for integers, and "a~" for arrays,
        if you're unfamiliar with the old C-style jargon used in dataTables.js.  "aa~" means
        "array of arrays".  In some instances, the author uses "ao~" for "array of objects", an
        object being a javascript dictionary.
        
        """
        
        object_list, total_records, unpaged_total = object_list
        
        response_obj = {
            'sEcho': self.request.GET.get('sEcho', None),
            'iTotalRecords': total_records,
            'iTotalDisplayRecords': unpaged_total,
            'aaData': [self.get_record_data(obj) for obj in object_list],
        }
        
        return json.dumps(response_obj, indent=4)
    
    def get_record_data(self, obj):
        """
        Returns a list of column data intended to be passed directly back to dataTables.js.
        
        Each column generates a 2-tuple of data. [0] is the data meant to be displayed to the client
        and [1] is the data in plain-text form, meant for manual searches.  One wouldn't want to
        include HTML in [1], for example.
        
        """
        
        options = self.get_datatable_options()
        
        data = []
        for i, name in enumerate(options.columns):
            data.append(self.get_column_data(i, name, obj)[0])
        
        return data
    
    def get_column_data(self, i, name, instance):
        """ Finds the backing method for column ``name`` and returns the generated data. """
        is_custom, f = self._get_resolver_method(i, name)
            
        if is_custom:
            values = f(instance, *self._get_preloaded_data(instance))
        else:
            values = f(instance, name)
        
        if not isinstance(values, (tuple, list)):
            values = (values, re.sub(r'<[^>]+>', '', values))
        
        return values
    
    def preload_record_data(self, instance):
        """
        An empty hook for letting the view do something with ``instance`` before column lookups are
        called against the object.  The tuple of items returned will be passed as positional
        arguments to any of the ``get_column_FIELD_NAME_data()`` methods.
        
        """
        
        return ()
    
    def _get_preloaded_data(self, instance):
        """ Fetches value from ``preload_record_data()`` and ensures it's a tuple. """
        preloaded_data = self.preload_record_data(instance)
        if not isinstance(preloaded_data, (tuple, list)):
            preloaded_data = (preloaded_data,)
        return preloaded_data
        
    def _get_resolver_method(self, i, name):
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
        
        if isinstance(name, (tuple, list)):
            if len(name) == 3:
                # Method name is explicitly given
                method_name = name[2]
                if callable(method_name):
                    return True, method_name
                return True, getattr(self, method_name)
            
            # Treat the 'nice name' as the starting point for looking up a method
            name = name[0]
        mangled_name = re.sub(r'[\W_]+', '_', name)
            
        f = getattr(self, 'get_column_%s_data' % mangled_name, None)
        if f:
            return True, f
        
        f = getattr(self, 'get_column_%d_data' % i, None)
        if f:
            return True, f
        
        return False, self._get_column_data_default
        
    
    def _get_column_data_default(self, instance, name):
        """ Default mechanism for resolving ``name`` through the model instance ``obj``. """
        
        def chain_lookup(obj, bit):
            value = getattr(obj, bit)
            if isinstance(value, Manager):
                value = value.all()
            if callable(value):
                value = value()
            return value
        
        
        if isinstance(name, (tuple, list)):
            name, field_lookup = name[0], name[1]
        else:
            field_lookup = name
        
        value = reduce(chain_lookup, [instance] + field_lookup.split('__'))
        
        if isinstance(value, Model):
            value = unicode(value)
        
        return value, value
    

class DatatableView(DatatableMixin, ListView):
    pass
