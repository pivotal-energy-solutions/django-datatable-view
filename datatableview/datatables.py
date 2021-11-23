# -*- coding: utf-8 -*-

import re
import copy
import operator
from collections import OrderedDict

from django.core.exceptions import FieldDoesNotExist

from functools import reduce

from django.template.loader import render_to_string
from django.db.models import QuerySet
from django.utils.encoding import force_str

from .exceptions import ColumnError, SkipRecord
from .columns import (
    Column,
    TextColumn,
    DateColumn,  # noqa: F401
    DateTimeColumn,  # noqa: F401
    BooleanColumn,  # noqa: F401
    IntegerColumn,  # noqa: F401
    FloatColumn,  # noqa: F401
    DisplayColumn,  # noqa: F401
    CompoundColumn,  # noqa: F401
    get_column_for_modelfield,
)  # noqa: F401

from .utils import (
    OPTION_NAME_MAP,
    MINIMUM_PAGE_LENGTH,
    contains_plural_field,
    split_terms,
    resolve_orm_path,
)
from .cache import DEFAULT_CACHE_TYPE, cache_types, get_cache_key, cache_data, get_cached_data


def pretty_name(name):
    if not name:
        return ""
    return name[0].capitalize() + name[1:]


# Borrowed from the Django forms implementation
def columns_for_model(
    model, fields=None, exclude=None, labels=None, processors=None, unsortable=None, hidden=None
):
    field_list = []
    opts = model._meta
    for f in sorted(opts.fields):
        if fields is not None and f.name not in fields:
            continue
        if exclude and f.name in exclude:
            continue

        column_class = get_column_for_modelfield(f)
        if column_class is None:
            raise ColumnError("Unhandled model field %r." % (f,))
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
        column = column_class(
            sources=[f.name], label=label, processor=processor, sortable=sortable, visible=visible
        )
        column.name = f.name
        field_list.append((f.name, column))

    field_dict = OrderedDict(field_list)
    if fields:
        field_dict = OrderedDict(
            [
                (f, field_dict.get(f))
                for f in fields
                if (not exclude) or (exclude and f not in exclude)
            ]
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
        (column_name, attrs.pop(column_name))
        for column_name, obj in list(attrs.items())
        if isinstance(obj, Column)
    ]
    local_columns.sort(key=lambda x: x[1].creation_counter)

    # If this class is subclassing another Form, add that Form's columns.
    # Note that we loop over the bases in *reverse*. This is necessary in
    # order to preserve the correct order of columns.
    if with_base_columns:
        for base in bases[::-1]:
            if hasattr(base, "base_columns"):
                local_columns = list(base.base_columns.items()) + local_columns
    else:
        for base in bases[::-1]:
            if hasattr(base, "declared_columns"):
                local_columns = list(base.declared_columns.items()) + local_columns

    return OrderedDict(local_columns)


class DatatableOptions(object):
    """
    Contains declarable options for a datatable, some of which can be manipuated by subsequent
    requests by the user.
    """

    def __init__(self, options=None):
        # Non-mutable; server's declared preference is final
        self.id = getattr(options, "id", "")
        self.model = getattr(options, "model", None)
        self.columns = getattr(options, "columns", None)  # table headers
        self.exclude = getattr(options, "exclude", None)
        self.search_fields = getattr(options, "search_fields", None)  # extra searchable ORM fields
        self.unsortable_columns = getattr(options, "unsortable_columns", None)
        self.hidden_columns = getattr(options, "hidden_columns", None)  # generated, but hidden
        self.labels = getattr(options, "labels", None)
        self.processors = getattr(options, "processors", None)
        self.request_method = getattr(options, "request_method", "GET")
        self.structure_template = getattr(
            options, "structure_template", "datatableview/default_structure.html"
        )
        self.footer = getattr(options, "footer", False)
        self.result_counter_id = getattr(options, "result_counter_id", "id_count")

        # Non-mutable; server behavior customization
        self.cache_type = getattr(options, "cache_type", cache_types.NONE)
        self.cache_queryset_count = getattr(options, "cache_queryset_count", False)

        # Mutable by the request
        self.ordering = getattr(options, "ordering", None)  # override to Model._meta.ordering
        self.page_length = getattr(options, "page_length", 25)  # length of a single result page


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

        opts = new_class._meta = new_class.options_class(getattr(new_class, "Meta", None))
        if opts.model:
            columns = columns_for_model(
                opts.model,
                opts.columns,
                opts.exclude,
                opts.labels,
                opts.processors,
                opts.unsortable_columns,
                opts.hidden_columns,
            )
            none_model_columns = [k for k, v in columns.items() if not v]
            missing_columns = set(none_model_columns) - set(declared_columns.keys())

            for name, column in declared_columns.items():
                column.name = name
                # if not column.sources:
                #     column.sources = [name]
                if not column.label:
                    try:
                        field = resolve_orm_path(opts.model, name)
                    except FieldDoesNotExist:
                        label = name
                    else:
                        label = field.verbose_name
                    column.label = pretty_name(label)

            # Normalize declared 'search_fields' to Column instances
            if isinstance(opts.search_fields, dict):
                # Turn a dictionary of {name: ColumnClass} to just a list of classes.
                # If only the column class reference is given instead of an instance, instantiate
                # the object first.
                search_fields = []
                for name, column in opts.search_fields.items():
                    if callable(column):
                        column = column(sources=[name])
                    search_fields.append(column)
                opts.search_fields = search_fields
            elif opts.search_fields is None:
                opts.search_fields = []
            else:
                opts.search_fields = list(opts.search_fields)
            for i, column in enumerate(opts.search_fields):
                # Build a column object
                if isinstance(column, str):
                    name = column
                    field = resolve_orm_path(opts.model, name)
                    column = get_column_for_modelfield(field)
                    opts.search_fields[i] = column(sources=[name])

            columns.update(declared_columns)
        else:
            columns = declared_columns
            missing_columns = []

        new_class.declared_columns = declared_columns
        new_class.base_columns = columns
        new_class.missing_columns = missing_columns
        return new_class


class Datatable(metaclass=DatatableMetaclass):
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

    def __init__(
        self,
        object_list,
        url,
        view=None,
        callback_target=None,
        model=None,
        query_config=None,
        force_distinct=True,
        **kwargs,
    ):
        self.object_list = object_list
        self.url = url
        self.view = view
        self.forward_callback_target = callback_target
        self.model = model or self._meta.model
        if self.model is None and hasattr(object_list, "model"):
            self.model = object_list.model
        if query_config is None:
            query_config = {}
        self.query_config = query_config

        self.columns = copy.deepcopy(self.base_columns)

        self._force_distinct = force_distinct
        self.total_initial_record_count = None
        self.unpaged_record_count = None

    def configure(self):
        """
        Combines (in order) the declared/inherited inner Meta, any view options, and finally any
        valid AJAX GET parameters from client modifications to the data they see.
        """

        if hasattr(self, "_configured"):
            return

        self.resolve_virtual_columns(*tuple(self.missing_columns))

        self.config = self.normalize_config(self._meta.__dict__, self.query_config)

        self.config["column_searches"] = {}
        for i, name in enumerate(self.columns.keys()):
            column_search = self.query_config.get(OPTION_NAME_MAP["search_column"] % i, None)
            if column_search:
                self.config["column_searches"][name] = column_search

        column_order = list(self.columns.keys())
        if self.config["ordering"]:
            for i, name in enumerate(self.config["ordering"]):
                column_name = name.lstrip("-+")
                try:
                    index = column_order.index(column_name)
                except ValueError:
                    # It is important to ignore a bad ordering name, since the model.Meta may
                    # specify a field name that is not present on the datatable columns list.
                    continue
                self.columns[column_name].sort_priority = i
                self.columns[column_name].sort_direction = "desc" if name[0] == "-" else "asc"
                self.columns[column_name].index = index

        for name in self.config["hidden_columns"]:
            self.columns[name].visible = False

        self._configured = True

    # Client request configuration mergers
    def normalize_config(self, config, query_config):
        """
        Merge the declared configuration with whatever valid query parameters are found from the
        client's AJAX request.
        """

        # Core options, not modifiable by client updates
        if config["hidden_columns"] is None:
            config["hidden_columns"] = []
        if config["search_fields"] is None:
            config["search_fields"] = []
        if config["unsortable_columns"] is None:
            config["unsortable_columns"] = []

        config["search"] = self.normalize_config_search(config, query_config)
        config["start_offset"] = self.normalize_config_start_offset(config, query_config)
        config["page_length"] = self.normalize_config_page_length(config, query_config)
        config["ordering"] = self.normalize_config_ordering(config, query_config)
        self._ordering_columns = self.ensure_ordering_columns(config["ordering"])

        return config

    def normalize_config_search(self, config, query_config):
        terms_string = query_config.get(OPTION_NAME_MAP["search"], "").strip()
        return set(split_terms(terms_string))

    def normalize_config_start_offset(self, config, query_config):
        try:
            start_offset = query_config.get(OPTION_NAME_MAP["start_offset"], 0)
            start_offset = int(start_offset)
        except ValueError:
            start_offset = 0
        else:
            if start_offset < 0:
                start_offset = 0
        return start_offset

    def normalize_config_page_length(self, config, query_config):
        try:
            page_length = query_config.get(OPTION_NAME_MAP["page_length"], config["page_length"])
            page_length = int(page_length)
        except ValueError:
            page_length = config["page_length"]
        else:
            if page_length == -1:  # dataTables' way of asking for all items, no pagination
                pass
            elif page_length < MINIMUM_PAGE_LENGTH:
                page_length = MINIMUM_PAGE_LENGTH
        return page_length

    def normalize_config_ordering(self, config, query_config):
        default_ordering = config["ordering"]
        if default_ordering is None and config["model"]:
            default_ordering = config["model"]._meta.ordering

        sort_declarations = [k for k in query_config if re.match(r"^order\[\d+\]\[column\]$", k)]

        # Default sorting from view or model definition
        if len(sort_declarations) == 0:
            return default_ordering

        ordering = []
        columns_list = list(self.columns.values())

        for sort_queue_i in range(len(columns_list)):
            try:
                column_index = int(
                    query_config.get(OPTION_NAME_MAP["sort_column"] % sort_queue_i, "")
                )
            except ValueError:
                continue

            column = columns_list[column_index]

            # Reject requests for unsortable columns
            if column.name in config["unsortable_columns"]:
                continue

            sort_direction = query_config.get(
                OPTION_NAME_MAP["sort_column_direction"] % sort_queue_i, None
            )

            if sort_direction == "asc":
                sort_modifier = ""
            elif sort_direction == "desc":
                sort_modifier = "-"
            else:
                # Aggressively skip invalid specification
                continue

            ordering.append("%s%s" % (sort_modifier, column.name))

        if not ordering:
            return default_ordering
        return ordering

    def ensure_ordering_columns(self, ordering_names):
        if ordering_names is None:
            return {}

        # Normalize declared 'ordering' to Column instances
        ordering_columns = {}
        for i, name in enumerate(ordering_names):
            if name[0] in "+-":
                name = name[1:]

            if name not in self.columns:
                field = resolve_orm_path(self.model, name)
                column = get_column_for_modelfield(field)
                ordering_columns[name] = column(sources=[name])

        return ordering_columns

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
        if self.config["ordering"] is None:
            return [], []

        i = 0
        for i, name in enumerate(self.config["ordering"]):
            if name[0] in "+-":
                name = name[1:]
            if name in self.columns:
                column = self.columns[name]
            else:
                column = self._ordering_columns[name]
            if not column.get_db_sources(self.model):
                break
        else:
            i = len(self.config["ordering"])
        return self.config["ordering"][:i], self.config["ordering"][i:]

    def get_db_splits(self):
        """Legacy utility for fetching the database columns and non-database columns."""
        db_fields = []
        virtual_fields = []
        for name, column in self.columns.items():
            if column.get_db_sources():
                db_fields.append(name)
            else:
                virtual_fields.append(name)
        return db_fields, virtual_fields

    # Data retrieval
    def will_load_from_cache(self, **kwargs):
        """
        Returns a hint for external code concerning the presence of cache data for the given kwargs.

        See :py:meth:`.get_cache_key_kwargs` for information concerning the kwargs you must send for
        this hint to be accurate.
        """
        cached_data = self.get_cached_data(datatable_class=self.__class__, **kwargs)
        return not isinstance(cached_data, type(None))

    def get_cache_key_kwargs(self, view=None, user=None, **kwargs):
        """
        Returns the dictionary of kwargs that will be sent to :py:meth:`.get_cache_key` in order to
        generate a deterministic cache key.

        ``datatable_class``, ``view``, and ``user`` are returned by default, the user being looked
        up on the view's ``request`` attribute.

        Override this classmethod in order to add or remove items from the returned dictionary if
        you need a more specific or less specific cache key.
        """
        # Try to get user information if 'user' param is missing
        if hasattr(view, "request") and not user:
            user = view.request.user

        kwargs.update(
            {
                "datatable_class": self.__class__,
                "view": view,
                "user": user,
            }
        )

        return kwargs

    def get_cache_key(self, **kwargs):
        """
        Returns the full cache key used for object_list data handled by this datatable class.
        ``settings.DATATABLEVIEW_CACHE_PREFIX`` will be prepended to this value.

        The kwargs sent guarantee a deterministic cache key between requests.

        ``view`` and ``user`` are special kwargs that the caching system provides by default.  The
        view instance is inspected for its ``__module__.__name__`` string, and the user for its
        ``pk``.

        All other kwargs are hashed and appended to the cache key.
        """
        return get_cache_key(**kwargs)

    def get_cached_data(self, **kwargs):
        """Returns object_list data cached for the given kwargs."""
        return get_cached_data(self, **kwargs)

    def cache_data(self, data, **kwargs):
        """Caches object_list data for the given kwargs."""
        cache_data(self, data=data, **kwargs)

    def get_object_list(self):
        """
        Returns a cached object list if configured and available.  When no caching strategy is
        enabled or if the cached item is expired, the original ``object_list`` is returned.
        """

        # Initial object_list from constructor, before filtering or ordering.
        object_list = self.object_list

        # Consult cache, if enabled
        cache_type = self.config["cache_type"]
        if cache_type == cache_types.DEFAULT:
            cache_type = DEFAULT_CACHE_TYPE

        if cache_type:
            cache_kwargs = self.get_cache_key_kwargs(view=self.view)
            cached_data = self.get_cached_data(**cache_kwargs)

            # If no cache is available, simplify and store the original object_list
            if cached_data is None:
                cached_data = self.prepare_object_list_for_cache(cache_type, object_list)
                self.cache_data(cached_data, **cache_kwargs)

            object_list = self.expand_object_list_from_cache(cache_type, cached_data)

        return object_list

    def prepare_object_list_for_cache(self, cache_type, object_list):
        """
        Pre-caching hook that must prepare ``object_list`` for the cache using the strategy
        indicated by ``cache_type``, which is the table's ``Meta``
        :py:attr:`~datatableview.datatables.Meta.cache_type` value.

        When ``cache_type`` is ``SIMPLE``, the ``object_list`` is returned unmodified.

        When ``PK_LIST`` is used, ``object_list`` is queried for the list of ``pk`` values and those
        are returned instead.
        """
        data = object_list

        # Create the simplest reproducable query for repeated operations between requests
        # Note that 'queryset' cache_type is unhandled so that it passes straight through.
        if cache_type == cache_types.PK_LIST:
            # model = object_list.model
            data = tuple(object_list.values_list("pk", flat=True))

        # Objects in some other type of data structure should be pickable for cache backend
        return data

    def expand_object_list_from_cache(self, cache_type, cached_data):
        """
        Deserializes the ``cached_data`` fetched from the caching backend, according to the
        ``cache_type`` strategy that was used to originally store it.

        When ``cache_type`` is ``SIMPLE``, the ``cached_data`` is returned unmodified, since the
        ``object_list`` went into the cache unmodified.

        When ``PK_LIST`` is used, ``cached_data`` is treated as a list of ``pk`` values and is used
        to filter the model's default queryset to just those objects.
        """
        if cache_type == cache_types.PK_LIST:
            # Convert pk list back into queryset
            data = self.model.objects.filter(pk__in=cached_data)
        else:
            # Straight passthrough of cached items
            data = cached_data
        return data

    def _get_current_page(self):
        """
        If page_length is specified in the options or AJAX request, the result list is shortened to
        the correct offset and length.  Paged or not, the finalized object_list is then returned.
        """

        # Narrow the results to the appropriate page length for serialization
        if self.config["page_length"] != -1:
            i_begin = self.config["start_offset"]
            i_end = self.config["start_offset"] + self.config["page_length"]
            object_list = self._records[i_begin:i_end]
        else:
            object_list = self._records

        return object_list

    def get_records(self):
        """
        Calls :py:meth:`.populate_records` to apply searches and sorting to the object list, then
        extracts the applicate page of results, calling :py:meth:`.get_record_data` for each result
        in the page.

        Returns the final list of processed results.
        """
        if not hasattr(self, "_records"):
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
        Searches and sorts the original object list.  Even though these operations do not themselves
        generate queries, the original object list will be counted and the filtered object list will
        also be counted, meaning that this is the method is guaranteed to run queries.

        No paging will take place at this stage!
        """
        if not hasattr(self, "config"):
            self.configure()

        self._records = None
        base_objects = self.get_object_list()
        filtered_objects = self.search(base_objects)
        filtered_objects = self.sort(filtered_objects)
        self._records = filtered_objects

        num_total, num_filtered = self.count_objects(base_objects, filtered_objects)
        self.total_initial_record_count = num_total
        self.unpaged_record_count = num_filtered

    def count_objects(self, base_objects, filtered_objects):
        """
        Calculates object totals for datatable footer.  Returns a 2-tuple of counts for,
        respectively, the total number of objects and the filtered number of objects.

        Up to two ``COUNT`` queries may be issued.  If you already have heavy backend queries, this
        might add significant overhead to every ajax fetch, such as keystroke filters.

        If ``Meta.cache_type`` is configured and ``Meta.cache_queryset_count`` is set to True, the
        resulting counts will be stored in the caching backend.
        """

        num_total = None
        num_filtered = None

        if isinstance(base_objects, QuerySet):
            if self.config["cache_queryset_count"]:
                cache_kwargs = self.get_cache_key_kwargs(view=self.view, __num_total="__num_total")
                num_total = self.get_cached_data(**cache_kwargs)

            if num_total is None:
                num_total = base_objects.count()
                if self.config["cache_queryset_count"]:
                    self.cache_data(num_total, **cache_kwargs)
        else:
            num_total = len(base_objects)

        if len(self.config["search"]) > 0 or len(self.config["column_searches"]) > 0:
            if isinstance(filtered_objects, QuerySet):
                num_filtered = filtered_objects.count()
            else:
                num_filtered = len(filtered_objects)
        else:
            num_filtered = num_total

        return num_total, num_filtered

    def search(self, queryset):
        """Performs db-only queryset searches."""

        table_queries = []

        searches = {}

        # Add per-column searches where necessary
        for name, term in self.config["column_searches"].items():
            for term in set(split_terms(term)):
                columns = searches.setdefault(term, {})
                columns[name] = self.columns[name]

        # Global search terms apply to all columns
        for term in self.config["search"]:
            # NOTE: Allow global terms to overwrite identical queries that were single-column
            searches[term] = self.columns.copy()
            searches[term].update(
                {column.sources[0]: column for column in self.config["search_fields"]}
            )

        for term in searches.keys():
            term_queries = []
            for name, column in searches[term].items():
                if name is None:  # config.search_fields items
                    search_f = self._search_column
                else:
                    search_f = getattr(self, "search_%s" % (name,), self._search_column)
                q = search_f(column, term)
                if q is not None:
                    term_queries.append(q)
            if term_queries:
                table_queries.append(reduce(operator.or_, term_queries))

        if table_queries:
            q = reduce(operator.and_, table_queries)
            queryset = queryset.filter(q)

        return queryset.distinct()

    def _search_column(self, column, terms):
        """Requests search queries to be performed against the target column."""
        return column.search(self.model, terms)

    def sort(self, queryset):
        """
        Performs db-only queryset sorts, then applies manual sorts if required.
        """
        fields = []
        db, virtual = self.get_ordering_splits()
        for name in db:
            sort_direction = ""
            if name[0] in "+-":
                sort_direction = name[0]
                if sort_direction == "+":
                    sort_direction = ""
                name = name[1:]
            if name in self.columns:
                column = self.columns[name]
            else:
                column = self._ordering_columns[name]
            sources = column.get_sort_fields(self.model)
            if sources:
                fields.extend([(sort_direction + source) for source in sources])

        object_list = queryset.order_by(*fields)

        # When sorting a plural relationship field, we get duplicate rows for each item on the other
        # end of that relationship, which can't be removed with a call to distinct().
        if self._force_distinct and contains_plural_field(self.model, fields):
            object_list = self.force_distinct(object_list)

        if virtual:
            # Have to sort the whole queryset by hand!
            object_list = list(object_list)

            def flatten(value):
                if isinstance(value, (list, tuple)):
                    return flatten(value[0])
                return value

            for name in virtual[::-1]:  # stable sorting, top priority sort comes last
                reverse = False
                if name[0] in "+-":
                    reverse = name[0] == "-"
                    name = name[1:]
                column = self.columns[name]
                object_list.sort(key=lambda o: flatten(column.value(o)[0]), reverse=reverse)

        return object_list

    def force_distinct(self, object_list):
        seen = set()

        def is_unseen(obj):
            if obj.pk in seen:
                return False
            seen.add(obj.pk)
            return True

        return tuple(obj for obj in object_list if is_unseen(obj))

    # Per-record callbacks
    def preload_record_data(self, obj):
        """
        An empty hook for doing something with a result ``obj`` before column lookups are called
        against the object.  The dict of items returned will be passed as keyword arguments to any
        available column ``processor`` callbacks.

        Use this to look up expensive data once per record so that it can be shared between column
        processors.

        By default, this method also inspects the originating view for a method of the same name,
        giving it an opportunity to contribute to the preloaded data.
        """

        kwargs = {}
        if self.forward_callback_target and hasattr(
            self.forward_callback_target, "preload_record_data"
        ):
            kwargs.update(self.forward_callback_target.preload_record_data(obj))
        return kwargs

    def get_object_pk(self, obj):
        """Returns the object's ``pk`` value."""
        return obj.pk

    def get_extra_record_data(self, obj):
        """Returns a dictionary of JSON-friendly data sent to the client as ``"DT_RowData"``."""
        data = {}
        if self.forward_callback_target and hasattr(
            self.forward_callback_target, "get_extra_record_data"
        ):
            data.update(self.forward_callback_target.get_extra_record_data(obj))
        return data

    def get_record_data(self, obj):
        """
        Returns a dict of column data that will be given to the view for final serialization.  The
        key names in this dict are not finalized at this stage, but all of the data is present.

        Each column is consulted for its value (computed based on its
        :py:attr:`~datatableview.columns.Column.sources` applied against the given ``obj`` instance)
        and then sent to the column's :py:attr:`~datatableview.columns.Column.processor` function.
        """

        preloaded_kwargs = self.preload_record_data(obj)
        data = {
            "pk": self.get_object_pk(obj),
            "_extra_data": self.get_extra_record_data(obj),
        }
        for i, (name, column) in enumerate(self.columns.items()):
            kwargs = dict(
                column.get_processor_kwargs(**preloaded_kwargs),
                **{
                    "datatable": self,
                    "view": self.view,
                    "field_name": column.name,
                },
            )
            value = self.get_column_value(obj, column, **kwargs)
            processor = self.get_processor_method(column, i)
            if processor:
                value = processor(obj, default_value=value[0], rich_value=value[1], **kwargs)

            # A 2-tuple at this stage has presumably served its purpose in the processor callback,
            # so we convert it to its "rich" value for display purposes.
            if isinstance(value, (tuple, list)):
                value = value[1]

            if value is not None:
                value = str(value)
            data[str(i)] = value
        return data

    def get_column_value(self, obj, column, **kwargs):
        """Returns whatever the column derived as the source value."""
        return column.value(obj, **kwargs)

    def get_processor_method(self, column, i):
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

        column_name = column.name
        if isinstance(self, LegacyDatatable):
            name = force_str(column.label, errors="ignore")
            if not name:
                name = column.sources[0]
            column_name = re.sub(r"[\W_]+", "_", name)

        if self.forward_callback_target:
            f = getattr(self.forward_callback_target, "get_column_%s_data" % (column_name,), None)
            if f:
                return f

            f = getattr(self.forward_callback_target, "get_column_%d_data" % (i,), None)
            if f:
                return f

        f = getattr(self, "get_column_%s_data" % (column_name,), None)
        if f:
            return f

        f = getattr(self, "get_column_%d_data" % (i,), None)
        if f:
            return f

        return None

    # Template rendering features
    def __str__(self):
        """Renders ``structure_template`` with ``self`` as a context variable."""

        if not hasattr(self, "config"):
            self.configure()

        context = {
            "url": self.url,
            "config": self.config,
            "datatable": self,
            "columns": self.columns.values(),
        }
        return render_to_string(self.config["structure_template"], context)

    def __iter__(self):
        """Yields each column in order."""

        if not hasattr(self, "config"):
            self.configure()

        for column in self.columns.values():
            yield column


class ValuesDatatable(Datatable):
    """
    Variant of the standard Datatable that terminates its queryset with ``.values()`` provides the
    results to any column :py:attr:`~datatableview.columns.Column.processor` callbacks for
    additional modification.

    Processor callbacks will no longer receive model instances, but instead the dict of selected
    values.
    """

    def get_valuesqueryset(self, queryset):
        # Figure out the full list of ORM path names
        self.value_queries = OrderedDict({"pk": "pk"})
        for name, column in self.columns.items():
            self.value_queries.update(OrderedDict([(source, name) for source in column.sources]))

        return queryset.values(*self.value_queries.keys())

    def populate_records(self):
        """
        Switches the original queryset to a ``ValuesQuerySet``, selecting values according to what
        each column has declared in its :py:attr:`~datatableview.columns.Column.sources` list.
        """

        self.object_list = self.get_valuesqueryset(self.object_list)
        super(ValuesDatatable, self).populate_records()

    def get_object_pk(self, obj):
        """
        Correctly reads the pk from the ValuesQuerySet entry, as a dict item instead of an
        attribute.
        """
        return obj["pk"]

    def preload_record_data(self, obj):
        """
        Modifies the ``obj`` values dict to alias the selected values to the column name that asked
        for its selection.

        For example, a datatable that declares a column ``'blog'`` which has a related lookup source
        ``'blog__name'`` will ensure that the selected value exists in ``obj`` at both keys
        ``blog__name`` and ``blog`` (the former because that was how it was selected, the latter
        because that was the column name used to select it).

        :Example:

            ``{'pk': 1, 'blog__name': "My Blog"}``
            ``{'pk': 1: 'blog__name': "My Blog", 'blog': "My Blog"}``

        When a column declares multiple :py:attr:`~datatableview.columns.Column.sources`, the column
        name's entry in ``obj`` will be a list of each of those values.

        :Example:

            ``{'pk': 1, 'blog__name': "My Blog", 'blog__id': 5}``
            ``{'pk': 1: 'blog__name': "My Blog", 'blog__id': 5, 'blog': ["My Blog", 5]}``

        In every situation, the original selected values will always be retained in ``obj``.
        """
        data = {}

        for orm_path, column_name in self.value_queries.items():
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
    """
    Modifies the :py:meth:`.resolve_virtual_columns` hook to deal with legacy-style column
    declarations, rather than automatically raising them as errors like normal.

    :py:class:`~datatableview.views.legacy.LegacyDatatableView` automatically uses this
    as its :py:attr:`~datatableview.views.legacy.LegacyDatatableView.datatable_class`.
    """

    def resolve_virtual_columns(self, *names):
        """
        Assume that all ``names`` are legacy-style tuple declarations, and generate modern columns
        instances to match the behavior of the old syntax.
        """
        from .views.legacy import get_field_definition

        virtual_columns = {}
        for name in names:
            field = get_field_definition(name)
            column = TextColumn(
                sources=field.fields, label=field.pretty_name, processor=field.callback
            )
            column.name = field.pretty_name if field.pretty_name else field.fields[0]
            virtual_columns[name] = column

        # Make sure it's in the same order as originally defined
        new_columns = OrderedDict()
        for name in self._meta.columns:  # Can't use self.config yet, hasn't been generated
            if self.columns.get(name):
                column = self.columns[name]
            else:
                column = virtual_columns[name]
            new_columns[column.name] = column
        self.columns = new_columns


class ValuesLegacyDatatable(LegacyDatatable, ValuesDatatable):
    """
    A :py:class:`LegacyDatatable` that also inherits from :py:class:`ValuesDatatable`
    """
