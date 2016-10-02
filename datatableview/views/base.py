# -*- encoding: utf-8 -*-

import json
import logging

from django.views.generic import ListView, TemplateView
from django.views.generic.list import MultipleObjectMixin
from django.http import HttpResponse
from django.conf import settings

from ..datatables import Datatable, DatatableOptions

log = logging.getLogger(__name__)


class DatatableJSONResponseMixin(object):
    # AJAX response router
    def get(self, request, *args, **kwargs):
        """
        Detects AJAX access and returns appropriate serialized data.  Normal access to the view is
        unmodified.
        """

        if request.is_ajax() or request.GET.get('ajax') == 'true':
            return self.get_ajax(request, *args, **kwargs)
        return super(DatatableJSONResponseMixin, self).get(request, *args, **kwargs)

    # Response generation
    def get_json_response_object(self, datatable):
        """
        Returns the JSON-compatible dictionary that will be serialized for an AJAX response.

        The value names are in the form "s~" for strings, "i~" for integers, and "a~" for arrays,
        if you're unfamiliar with the old C-style jargon used in dataTables.js.  "aa~" means
        "array of arrays".  In some instances, the author uses "ao~" for "array of objects", an
        object being a javascript dictionary.
        """

        # Ensure the object list is calculated.
        # Calling get_records() will do this implicitly, but we want simultaneous access to the
        # 'total_initial_record_count', and 'unpaged_record_count' values.
        datatable.populate_records()

        response_data = {
            'draw': self.request.GET.get('draw', None),
            'recordsFiltered': datatable.total_initial_record_count,
            'recordsTotal': datatable.unpaged_record_count,
            'data': [dict(record, **{
                'DT_RowId': record.pop('pk'),
                'DT_RowData': record.pop('_extra_data'),
            }) for record in datatable.get_records()],
        }
        return response_data

    def serialize_to_json(self, response_data):
        """ Returns the JSON string for the compiled data object. """

        indent = None
        if settings.DEBUG:
            indent = 4

        return json.dumps(response_data, indent=indent)


class DatatableMixin(DatatableJSONResponseMixin, MultipleObjectMixin):
    """
    Adds a JSON AJAX response mechanism that can be used by the datatables.js code to load
    server-side records.
    """

    datatable_class = None
    context_datatable_name = 'datatable'

    # AJAX response handler
    def get_ajax(self, request, *args, **kwargs):
        """ Called in place of normal ``get()`` when accessed via AJAX. """

        datatable = self.get_datatable()
        datatable.configure()
        response_data = self.get_json_response_object(datatable)
        response = HttpResponse(self.serialize_to_json(response_data),
                                content_type="application/json")

        return response

    # Configuration getters
    def get_datatable(self, **kwargs):
        """ Gathers and returns the final :py:class:`Datatable` instance for processing. """
        datatable_class = self.get_datatable_class()
        if datatable_class is None:
            class AutoMeta:
                model = self.model or self.get_queryset().model
            opts = AutoMeta()
            datatable_class = Datatable
        else:
            opts = datatable_class.options_class(datatable_class._meta)

        kwargs = self.get_datatable_kwargs(**kwargs)
        for meta_opt in opts.__dict__:
            if meta_opt in kwargs:
                setattr(opts, meta_opt, kwargs.pop(meta_opt))

        datatable_class = type('%s_Synthesized' % (datatable_class.__name__,), (datatable_class,), {
            'Meta': opts,
        })
        return datatable_class(**kwargs)

    def get_datatable_class(self):
        return self.datatable_class

    def get_datatable_kwargs(self, **kwargs):
        queryset = self.get_queryset()
        kwargs.update({
            'object_list': queryset,
            'view': self,
            'model': self.model or queryset.model,
        })

        # This is provided by default, but if the view is instantiated outside of the request cycle
        # (such as for the purposes of embedding that view's datatable elsewhere), the request may
        # not be required, so the user may not have a compelling reason to go through the trouble of
        # putting it on self.
        if hasattr(self, 'request'):
            kwargs['url'] = self.request.path
            kwargs['query_config'] = self.request.GET
        else:
            kwargs['query_config'] = {}

        settings = ('columns', 'exclude', 'ordering', 'start_offset', 'page_length', 'search',
                    'search_fields', 'unsortable_columns', 'hidden_columns', 'footer',
                    'structure_template', 'result_counter_id')
        
        for k in settings:
            if hasattr(self, k):
                kwargs[k] = getattr(self, k)
        return kwargs


    # Runtime per-object hook
    def preload_record_data(self, obj):
        return {}

    # Extra getters
    def get_datatable_context_name(self):
        return self.context_datatable_name

    def get_context_data(self, **kwargs):
        context = super(DatatableMixin, self).get_context_data(**kwargs)

        context[self.get_datatable_context_name()] = self.get_datatable()

        return context


class DatatableView(DatatableMixin, ListView):
    """ Implements :py:class:`DatatableMixin` and the standard Django ``ListView``. """


class MultipleDatatableMixin(DatatableJSONResponseMixin):
    """
    Allow multiple Datatable classes to be given as a dictionary of context names to classes.

    Methods will be dynamically inspected to supply the classes with a queryset and their
    initialization kwargs, in the form of ``get_FOO_datatable_queryset(**kwargs)`` or
    ``get_FOO_datatable_kwargs(**kwargs)`` respectively.

    In the case of the kwargs getter, the default generated kwargs can be retrieved via a call to
    ``get_default_datatable_kwargs(**kwargs)``, where ``**kwargs`` is a reference to the kwargs that
    came into the ``get_FOO_datatable_kwargs(**kwargs)`` method.
    """

    datatable_classes = None  # Dict of context names to class names

    # AJAX response handler
    def get_ajax(self, request, *args, **kwargs):
        """ Called in place of normal ``get()`` when accessed via AJAX. """

        datatable = self.get_active_ajax_datatable()
        datatable.configure()
        response_data = self.get_json_response_object(datatable)
        response = HttpResponse(self.serialize_to_json(response_data),
                                content_type="application/json")

        return response

    # Configuration getters
    def get_datatables(self, only=None):
        """ Returns a dict of the datatables served by this view. """
        if not hasattr(self, '_datatables'):
            self._datatables = {}
            datatable_classes = self.get_datatable_classes()
            for name, datatable_class in datatable_classes.items():
                if only and name != only:
                    continue
                queryset_getter_name = 'get_%s_datatable_queryset' % (name,)
                queryset_getter = getattr(self, queryset_getter_name, None)
                if queryset_getter is None:
                    raise ValueError("%r must declare a method %r." % (self.__class__.__name__,
                                                                       queryset_getter_name))

                queryset = queryset_getter()
                if datatable_class is None:
                    class AutoMeta:
                        model = queryset.model
                    datatable_class = type('%sDatatable' % (self.__class__.__name__,), (Datatable,), {
                        'Meta': AutoMeta,
                    })
                elif datatable_class._meta.model is None:
                    opts = datatable_class.options_class(datatable_class._meta)
                    opts.model = queryset.model
                    datatable_class = type('%s_WithModel' % (datatable_class.__name__,), (datatable_class,), {
                        'Meta': opts,
                    })

                default_kwargs = {
                    'object_list': queryset,
                }
                kwargs_getter_name = 'get_%s_datatable_kwargs' % (name,)
                kwargs_getter = getattr(self, kwargs_getter_name, self.get_default_datatable_kwargs)
                kwargs = kwargs_getter(**default_kwargs)
                if 'url' in kwargs:
                    kwargs['url'] = kwargs['url'] + "?datatable=%s" % (name,)
                self._datatables[name] = datatable_class(**kwargs)
        return self._datatables

    def get_datatable_classes(self):
        """ Return a shallow copy of the view's ``datatable_classes`` dict. """
        if self.datatable_classes is None:
            return {}
        return dict(self.datatable_classes)

    def get_default_datatable_kwargs(self, **kwargs):
        """
        Builds the default set of kwargs for initializing a Datatable class.  Note that by default
        the MultipleDatatableMixin does not support any configuration via the view's class
        attributes, and instead relies completely on the Datatable class itself to declare its
        configuration details.
        """

        kwargs['view'] = self

        # This is provided by default, but if the view is instantiated outside of the request cycle
        # (such as for the purposes of embedding that view's datatable elsewhere), the request may
        # not be required, so the user may not have a compelling reason to go through the trouble of
        # putting it on self.
        if hasattr(self, 'request'):
            kwargs['url'] = self.request.path
            kwargs['query_config'] = self.request.GET
        else:
            kwargs['query_config'] = {}

        return kwargs

    def get_active_ajax_datatable(self):
        """ Returns a single datatable according to the hint GET variable from an AJAX request. """
        datatables_dict = self.get_datatables(only=self.request.GET['datatable'])
        return list(datatables_dict.values())[0]

    # Extra getters
    def get_context_data(self, **kwargs):
        context = super(MultipleDatatableMixin, self).get_context_data(**kwargs)

        for name, datatable in self.get_datatables().items():
            context_name = '%s_datatable' % (name,)
            context[context_name] = datatable

        return context


class MultipleDatatableView(MultipleDatatableMixin, TemplateView):
    pass


