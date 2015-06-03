# -*- encoding: utf-8 -*-

import datetime
import json
from django.utils.encoding import force_text
import re
import operator
import logging
try:
    from functools import reduce
except ImportError:
    pass

from django.views.generic.list import ListView, MultipleObjectMixin
from django.http import HttpResponse, HttpResponseBadRequest
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model, Manager, Q
from django.utils.encoding import force_text
from django.utils.text import smart_split
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings
from django import get_version

import six
import dateutil.parser

from .forms import XEditableUpdateForm
from .utils import (FIELD_TYPES, ObjectListResult, DatatableOptions, DatatableStructure,
                    split_real_fields, filter_real_fields, resolve_orm_path, get_first_orm_bit,
                    get_field_definition)

log = logging.getLogger(__name__)


CAN_UPDATE_FIELDS = get_version().split('.') >= ['1', '5']

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
    datatable_options_class = DatatableOptions
    datatable_structure_class = DatatableStructure

    def get(self, request, *args, **kwargs):
        """
        Detects AJAX access and returns appropriate serialized data.  Normal access to the view is
        unmodified.

        """

        if request.is_ajax() or request.GET.get('ajax') == 'true':
            return self.get_ajax(request, *args, **kwargs)
        return super(DatatableMixin, self).get(request, *args, **kwargs)

    def get_model(self):
        if not self.model:
            self.model = self.get_queryset().model
        return self.model

    def get_object_list(self):
        """ Gets the core queryset, but applies the datatable options to it. """
        return self.apply_queryset_options(self.get_queryset())

    def get_ajax_url(self):
        return self.request.path

    def get_datatable_structure(self):
        options = self._get_datatable_options()
        model = self.get_model()
        return self.datatable_structure_class(self.get_ajax_url(), options, model=model)

    def get_datatable_options(self):
        """
        Returns the DatatableOptions object for this view's configuration.

        This method is guaranteed to be called only once per request.

        """

        return self.datatable_options

    def _get_datatable_options(self):
        """
        Internal safe access.  Guarantees that ``get_datatable_options()`` is called only once, so
        that subclasses can use that method to modify the class attribute ``datatable_options``.

        """

        if not hasattr(self, '_datatable_options'):
            model = self.get_model()

            options = self.get_datatable_options()
            if options:
                # Options are defined, but probably in a raw dict format
                options = self.datatable_options_class(model, self.request.GET, **dict(options))
            else:
                # No options defined on the view
                options = self.datatable_options_class(model, self.request.GET)

            self._datatable_options = options
        return self._datatable_options

    def apply_queryset_options(self, queryset):
        """
        Interprets the datatable options.

        Options requiring manual massaging of the queryset are handled here.  The output of this
        method should be treated as a list, since complex options might convert it out of the
        original queryset form.

        """

        options = self._get_datatable_options()

        # These will hold residue queries that cannot be handled in at the database level.  Anything
        # in these variables by the end will be handled manually (read: less efficiently)
        sort_fields = []
        searches = []

        # This count is for the benefit of the frontend datatables.js
        total_initial_record_count = queryset.count()

        if options['ordering']:
            db_fields, sort_fields = split_real_fields(self.get_model(), options['ordering'])
            queryset = queryset.order_by(*db_fields)

        if options['search']:
            db_fields, searches = filter_real_fields(self.get_model(), options['columns'],
                                                     key=get_first_orm_bit)
            db_fields.extend(options['search_fields'])

            queries = []  # Queries generated to search all fields for all terms
            search_terms = map(lambda q: q.strip("'\" "), smart_split(options['search']))

            for term in search_terms:
                term_queries = []  # Queries generated to search all fields for this term
                # Every concrete database lookup string in 'columns' is followed to its trailing field descriptor.  For example, "subdivision__name" terminates in a CharField.  The field type determines how it is probed for search.
                for column in db_fields:
                    column = get_field_definition(column)
                    for component_name in column.fields:
                        field_queries = []  # Queries generated to search this database field for the search term

                        field = resolve_orm_path(self.get_model(), component_name)
                        if field.choices:
                            # Query the database for the database value rather than display value
                            choices = field.get_flatchoices()
                            length = len(choices)
                            database_values = []
                            display_values = []

                            for choice in choices:
                                database_values.append(choice[0])
                                display_values.append(choice[1].lower())

                            for i in range(length):
                                if term.lower() in display_values[i]:
                                    field_queries = [{component_name + '__iexact': database_values[i]}]

                        elif isinstance(field, tuple(FIELD_TYPES['text'])):
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
                            except OverflowError:
                                # Catches OverflowError: signed integer is greater than maximum
                                pass
                            else:
                                field_queries.append({component_name: date_obj})

                            # Add queries for more granular date field lookups
                            try:
                                numerical_value = int(term)
                            except ValueError:
                                pass
                            else:
                                if datetime.MINYEAR < numerical_value < datetime.MAXYEAR - 1:
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

                        # print field_queries

                        # Append each field inspection for this term
                        term_queries.extend(map(lambda q: Q(**q), field_queries))
                # Append the logical OR of all field inspections for this term
                if len(term_queries):
                    queries.append(reduce(operator.or_, term_queries))
            # Apply the logical AND of all term inspections
            if len(queries):
                queryset = queryset.filter(reduce(operator.and_, queries))

        # Append distinct() to eliminate duplicate rows
        queryset = queryset.distinct()

        # TODO: Remove "and not searches" from this conditional, since manual searches won't be done
        if not sort_fields and not searches:
            # We can shortcut and speed up the process if all operations are database-backed.
            object_list = queryset
            if options['search']:
                object_list._dtv_unpaged_total = queryset.count()
            else:
                object_list._dtv_unpaged_total = total_initial_record_count
        else:
            object_list = ObjectListResult(queryset)

            # # Manual searches
            # # This is broken until it searches all items in object_list previous to the database
            # # sort. That represents a runtime load that hits every row in code, rather than in the
            # # database. If enabled, this would cripple performance on large datasets.
            # if options['i_walk_the_dangerous_line_between_genius_and_insanity']:
            #     length = len(object_list)
            #     for i, obj in enumerate(reversed(object_list)):
            #         keep = False
            #         for column_info in searches:
            #             column_index = options['columns'].index(column_info)
            #             rich_data, plain_data = self.get_column_data(column_index, column_info, obj)
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

            # Sort the results manually for whatever remaining sort options are left over
            def data_getter_orm(field_name):
                def key(obj):
                    try:
                        return reduce(getattr, [obj] + field_name.split('__'))
                    except (AttributeError, ObjectDoesNotExist):
                        return None
                return key

            def data_getter_custom(i):
                def key(obj):
                    rich_value, plain_value = self.get_column_data(i, options['columns'][i], obj)
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

            object_list._dtv_unpaged_total = len(object_list)

        object_list._dtv_total_initial_record_count = total_initial_record_count
        return object_list

    def get_datatable_context_name(self):
        return self.datatable_context_name

    def get_datatable(self):
        """
        Returns the helper object that can be used in the template to render the datatable skeleton.

        """
        return self.get_datatable_structure()

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
        total = object_list._dtv_total_initial_record_count
        filtered_total = object_list._dtv_unpaged_total
        response_data = self.get_json_response_object(object_list, total, filtered_total)
        response = HttpResponse(self.serialize_to_json(response_data),
                                content_type="application/json")

        return response

    def get_json_response_object(self, object_list, total, filtered_total):
        """
        Returns the JSON-compatible dictionary that will be serialized for an AJAX response.

        The value names are in the form "s~" for strings, "i~" for integers, and "a~" for arrays,
        if you're unfamiliar with the old C-style jargon used in dataTables.js.  "aa~" means
        "array of arrays".  In some instances, the author uses "ao~" for "array of objects", an
        object being a javascript dictionary.
        """

        object_list_page = self.paginate_object_list(object_list)

        response_obj = {
            'sEcho': self.request.GET.get('sEcho', None),
            'iTotalRecords': total,
            'iTotalDisplayRecords': filtered_total,
            'aaData': [self.get_record_data(obj) for obj in object_list_page],
        }
        return response_obj

    def paginate_object_list(self, object_list):
        """
        If page_length is specified in the options or AJAX request, the result list is shortened to
        the correct offset and length.  Paged or not, the finalized object_list is then returned.
        """

        options = self._get_datatable_options()

        # Narrow the results to the appropriate page length for serialization
        if options['page_length'] != -1:
            i_begin = options['start_offset']
            i_end = options['start_offset'] + options['page_length']
            object_list = object_list[i_begin:i_end]

        return object_list

    def serialize_to_json(self, response_data):
        """ Returns the JSON string for the compiled data object. """

        indent = None
        if settings.DEBUG:
            indent = 4

        return json.dumps(response_data, indent=indent)

    def get_record_data(self, obj):
        """
        Returns a list of column data intended to be passed directly back to dataTables.js.

        Each column generates a 2-tuple of data. [0] is the data meant to be displayed to the client
        and [1] is the data in plain-text form, meant for manual searches.  One wouldn't want to
        include HTML in [1], for example.

        """

        options = self._get_datatable_options()

        data = {
            'DT_RowId': obj.pk,
        }
        for i, name in enumerate(options['columns']):
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
            kwargs['view'] = self
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
        name = force_text(column.pretty_name, errors="ignore")
        if not name:
            name = column.fields[0]

        mangled_name = re.sub(r'[\W_]+', '_', force_text(name))

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


class XEditableMixin(object):
    xeditable_form_class = XEditableUpdateForm

    xeditable_fieldname_param = 'xeditable_field'  # GET parameter name used for choices ajax

    def get(self, request, *args, **kwargs):
        """ Introduces the ``ensure_csrf_cookie`` decorator and handles xeditable choices ajax. """
        if request.GET.get(self.xeditable_fieldname_param):
            return self.get_ajax_xeditable_choices(request, *args, **kwargs)

        # Doing this in the method body at runtime instead of at declaration-time helps prevent
        # collisions of other subclasses also trying to decorate their own get() methods.
        method = super(XEditableMixin, self).get
        method = ensure_csrf_cookie(method)
        return method(request, *args, **kwargs)

    def get_ajax_xeditable_choices(self, request, *args, **kwargs):
        """ AJAX GET handler for xeditable queries asking for field choice lists. """
        field_name = request.GET[self.xeditable_fieldname_param]
        # Sanitize the requested field name by limiting valid names to the datatable_options columns
        columns = self._get_datatable_options()['columns']
        for name in columns:
            if isinstance(name, (list, tuple)):
                name = name[1]
            if name == field_name:
                break
        else:
            return HttpResponseBadRequest()

        field = self.get_model()._meta.get_field_by_name(field_name)[0]

        choices = self.get_field_choices(field, field_name)
        return HttpResponse(json.dumps(choices))

    def post(self, request, *args, **kwargs):
        self.object_list = None
        form = self.get_xeditable_form(self.get_xeditable_form_class())
        if form.is_valid():
            obj = self.get_update_object(form)
            if obj is None:
                data = json.dumps({
                    'status': 'error',
                    'message': "Object does not exist."
                })
                return HttpResponse(data, content_type="application/json", status=404)
            return self.update_object(form, obj)
        else:
            data = json.dumps({
                'status': 'error',
                'message': "Invalid request",
                'form_errors': form.errors,
            })
            return HttpResponse(data, content_type="application/json", status=400)

    def get_xeditable_form_class(self):
        return self.xeditable_form_class

    def get_xeditable_form_kwargs(self):
        kwargs = {
            'model': self.get_queryset().model,
        }
        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.request.POST,
            })
        return kwargs

    def get_xeditable_form(self, form_class):
        return form_class(**self.get_xeditable_form_kwargs())

    def get_update_object(self, form):
        """
        Retrieves the target object based on the update form's ``pk`` and the table's queryset.
        """
        pk = form.cleaned_data['pk']
        queryset = self.get_queryset()
        try:
            obj = queryset.get(pk=pk)
        except queryset.model.DoesNotExist:
            obj = None

        return obj

    def update_object(self, form, obj):
        """ Saves the new value to the target object. """
        field_name = form.cleaned_data['name']
        value = form.cleaned_data['value']
        setattr(obj, field_name, value)
        save_kwargs = {}
        if CAN_UPDATE_FIELDS:
            save_kwargs['update_fields'] = [field_name]
        obj.save(**save_kwargs)

        data = json.dumps({
            'status': 'success',
        })
        return HttpResponse(data, content_type="application/json")

    def get_field_choices(self, field, field_name):
        """ Returns the valid choices for ``field``.  ``field_name`` is given for convenience. """
        if self.request.GET.get('select2'):
            names = ['id', 'text']
        else:
            names = ['value', 'text']
        return [dict(zip(names, choice)) for choice in field.choices]


class DatatableView(DatatableMixin, ListView):
    pass


class XEditableDatatableView(XEditableMixin, DatatableView):
    pass
