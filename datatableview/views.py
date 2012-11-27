import json
import re

from django.views.generic.list import ListView, MultipleObjectMixin
from django.http import HttpResponse
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model, Manager

from datatableview.utils import DatatableStructure, DatatableOptions, split_real_fields

class DatatableMixin(MultipleObjectMixin):
    """
    Converts a view into an AJAX interface for obtaining records via a session-stored configuration.
    
    The normal GET execution adds a ``DataTable`` object to the context which can be used to
    streamline the dumping of the HTML skeleton required for datatables.js to hook.  A ``DataTable``
    object doesn't hold any data, just a structure superficially generated from the options on the
    view.
    
    The template is responsible for making the AJAX request back to this view to populate the table
    with data.
    
    When data is requested, the current state snapshot is kept in the user's session dictionary, so
    that navigating away and back won't lose the current view of the data.  This includes the
    current page, sort direction, search terms, etc.
    
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
    
    def get_queryset(self):
        """ Considers ``self.datatable_options`` to create a queryset. """
        
        queryset = super(DatatableMixin, self).get_queryset()
        return self.apply_queryset_options(queryset)
    
    def get_datatable_options(self):
        """ Returns the session's options for this view's datatable. """
        session = self.request.session
        
        if 'datatables' not in session or not isinstance(session['datatables'], dict):
            session['datatables'] = dict()
        
        options = session['datatables'].get(self.request.path, None)
        
        if options is None:
            # No existing session options for this page
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
            
            # Store the proper DatatableOptions instance in the session for future use.
            session['datatables'][self.request.path] = options
        
        return options
    
    def apply_queryset_options(self, queryset):
        """
        Interprets the session's datatable options.
        
        Options requiring manual massaging of the queryset are handled here.  The output of this
        method should be treated as a list, since complex options might convert it out of the
        original queryset form.
        
        """
        
        options = self.get_datatable_options()
        
        # These will hold residue queries that cannot be handled in at the database level.  Anything
        # in these variables by the end will be handled manually (read: less efficiently)
        sort_fields = []
        filters = []
        
        if options.ordering:
            db_fields, sort_fields = split_real_fields(self.model, options.ordering)
            queryset = queryset.order_by(*db_fields)
        
        if options.filters:
            if isinstance(options.filters, dict):
                filters = options.filters.items()
            else:
                # sequence of 2-tuples
                filters = options.filters
            
            # The first field in a string like "description__icontains" determines if the lookup
            # is concrete (can be handled by the database query) or virtual.  A query such as
            # "foreignkey__virtualfield__icontains" is not supported.  A query such as
            # "virtualfield__icontains" IS supported but will be handled manually.
            key_function = lambda item: item[0].split('__')[0]
            
            db_filters, filters = filter_real_fields(self.model, filters, key=key_function)
            
            queryset = queryset.filter(**dict(db_filters))
        
        # Get ready to turn the results into a normal iterable, which might happen during any of the
        # following operations.
        object_list = queryset
        
        
        
        # Sort the results manually for whatever remaining sort options are left over
        # object_list = sorted(object_list, )
        
        # TODO: This is broken out to facilitate data validation, but we're not yet validating it.
        # TODO: This shouldn't take place unless all sorting is done.
        page_slice = slice(options.start_offset, options.start_offset + options.page_length)
        object_list = object_list[page_slice]
        
        return object_list
    
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
        
        queryset = self.get_queryset()
        response = HttpResponse(self.serialize_to_json(queryset), mimetype="application/json")
        
        return response
    
    def serialize_to_json(self, object_list):
        """
        Returns the JSON string object required for dataTables.js to do its job.
        
        The value names are in the form "s~" for strings, "i~" for integers, and "a~" for arrays,
        if you're unfamiliar with the old C-style jargon used in dataTables.js.  "aa~" means
        "array of arrays".  In some instances, the author uses "ao~" for "array of objects", an
        object being a javascript dictionary.
        
        """
        
        response_obj = {
            'sEcho': self.request.GET.get('sEcho', None),
            'iTotalRecords': '__totalrecords__', # FIXME
            'iTotalDisplayRecords': len(object_list),
            'aaData': [self.get_record_data(obj) for obj in object_list],
        }
        
        return json.dumps(response_obj)
    
    def get_record_data(self, obj):
        """
        Returns a list of column data intended to be passed directly back to dataTables.js.
        
        """
        
        preloaded_data = self.preload_record_data(obj)
        if not isinstance(preloaded_data, (tuple, list)):
            preloaded_data = (preloaded_data,)
        
        options = self.get_datatable_options()
        
        data = []
        for i, name in enumerate(options.columns):
            is_custom, f = self._get_resolver_method(i, name)
            
            if is_custom:
                value = f(obj, *preloaded_data)
            else:
                value = f(obj, name)
            data.append(value)
        
        return data
    
    def preload_record_data(self, instance):
        """
        An empty hook for letting the view do something with ``instance`` before column lookups are
        called against the object.  The tuple of items returned will be passed as positional
        arguments to any of the ``get_column_FIELD_NAME_data()`` methods.
        
        """
        
        return ()
    
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
            name, field_lookup = name
        else:
            field_lookup = name
        
        value = reduce(chain_lookup, [instance] + field_lookup.split('__'))
        
        if isinstance(value, Model):
            value = unicode(value)
        
        return value
    

class DatatableView(DatatableMixin, ListView):
    pass
