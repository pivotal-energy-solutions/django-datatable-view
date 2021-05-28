# -*- coding: utf-8 -*-

import re
import operator
from datetime import datetime
from functools import reduce
import logging

from django.db import models
from django.db.models import Model, Manager, Q
from django.core.exceptions import ObjectDoesNotExist, FieldDoesNotExist
from django.utils.encoding import smart_str
from django.utils.safestring import mark_safe
from django.forms.utils import flatatt
from django.template.defaultfilters import slugify

import dateutil.parser

from .utils import resolve_orm_path, DEFAULT_EMPTY_VALUE, DEFAULT_MULTIPLE_SEPARATOR

log = logging.getLogger(__name__)

# Registry of Column subclasses to their declared corresponding ModelFields.
# The registery is an ordered priority list, containing 2-tuples of a Column subclass and a list of
# classes that the column will service.
COLUMN_CLASSES = []

STRPTIME_PLACEHOLDERS = {
    "year": ("%y", "%Y"),
    "month": ("%m", "%b", "%B"),
    "day": ("%d",),  # '%a', '%A'),  # day names are hard because they depend on other date info
    "hour": ("%H", "%I"),
    "minute": ("%M",),
    "second": ("%S",),
    "week_day": ("%w",),
}


def register_simple_modelfield(model_field):
    column_class = get_column_for_modelfield(model_field)
    COLUMN_CLASSES.insert(0, (column_class, [model_field]))


def get_column_for_modelfield(model_field):
    """Return the built-in Column class for a model field class."""

    # If the field points to another model, we want to get the pk field of that other model and use
    # that as the real field.  It is possible that a ForeignKey points to a model with table
    # inheritance, however, so we need to traverse the internal OneToOneField as well, so this will
    # climb the 'pk' field chain until we have something real.
    while model_field.related_model:
        model_field = model_field.related_model._meta.pk
    for ColumnClass, modelfield_classes in COLUMN_CLASSES:
        if isinstance(model_field, tuple(modelfield_classes)):
            return ColumnClass


def get_attribute_value(obj, bit):
    try:
        value = getattr(obj, bit)
    except (AttributeError, ObjectDoesNotExist):
        value = None
    else:
        if callable(value) and not isinstance(value, Manager):
            if not hasattr(value, "alters_data") or value.alters_data is not True:
                value = value()
    return value


class ColumnMetaclass(type):
    """Column type for automatic registration of column types as ModelField handlers."""

    def __new__(cls, name, bases, attrs):
        new_class = super(ColumnMetaclass, cls).__new__(cls, name, bases, attrs)
        if new_class.model_field_class:
            COLUMN_CLASSES.insert(0, (new_class, [new_class.model_field_class]))
            if new_class.handles_field_classes:
                COLUMN_CLASSES.insert(0, (new_class, new_class.handles_field_classes))
        return new_class


# Corollary to django.forms.fields.Field
class Column(metaclass=ColumnMetaclass):
    """Generic table column using CharField for rendering."""

    model_field_class = None
    handles_field_classes = []

    lookup_types = ()

    # Tracks each time a Field instance is created. Used to retain order.
    creation_counter = 0

    def __init__(
        self,
        label=None,
        sources=None,
        processor=None,
        source=None,
        separator=DEFAULT_MULTIPLE_SEPARATOR,
        empty_value=DEFAULT_EMPTY_VALUE,
        model_field_class=None,
        sortable=True,
        visible=True,
        localize=False,
        allow_regex=False,
        allow_full_text_search=False,
    ):
        if model_field_class:
            self.model_field_class = model_field_class

        if source and sources:
            raise ValueError("Cannot provide 'source' and 'sources' at the same time.")

        if source:
            sources = source

        self.name = None  # Set outside, once the Datatable can put it there
        if label is not None:
            label = smart_str(label)
        self.sources = sources or []  # TODO: Process for real/virtual
        if not isinstance(self.sources, (tuple, list)):
            self.sources = [self.sources]
        self.separator = separator
        self.label = label
        self.empty_value = smart_str(empty_value)
        self.localize = localize
        self.sortable = sortable
        self.visible = visible
        self.processor = processor
        self.allow_regex = allow_regex
        self.allow_full_text_search = allow_full_text_search

        if not self.sources:
            self.sortable = False

        # To be filled in externally once the datatable has ordering figured out.
        self.sort_priority = None
        self.sort_direction = None
        self.index = None

        # Increase the creation counter, and save our local copy.
        self.creation_counter = Column.creation_counter
        Column.creation_counter += 1

    def __repr__(self):
        return '<%s.%s "%s">' % (self.__class__.__module__, self.__class__.__name__, self.label)

    def value(self, obj, **kwargs):
        """
        Calls :py:meth:`.get_initial_value` to obtain the value from ``obj`` that this column's
        :py:attr:`.sources` list describes.

        Any supplied ``kwargs`` are forwarded to :py:meth:`.get_initial_value`.

        Returns the 2-tuple of ``(plain_value, rich_value)`` for the inspection and serialization
        phases of serialization.
        """

        values = self.get_initial_value(obj, **kwargs)

        if not isinstance(values, (tuple, list)):
            values = (values, values)

        return values

    def get_initial_value(self, obj, **kwargs):
        """
        Builds a list of values provided by :py:attr:`.sources` looked up on the target ``obj``.
        Each source may provide a value as a 2-tuple of ``(plain_value, rich_value)``, where
        ``plain_value`` is the sortable raw value, and ``rich_value`` is possibly something else
        that can be coerced to a string for display purposes. The ``rich_value`` could also be a
        string with HTML in it.

        If no 2-tuple is given, then ``plain_value`` and ``rich_value`` are taken to be the same.

        Columns with multiple :py:attr:`.sources` will have their ``rich_value`` coerced to a string
        and joined with :py:attr:`.separator`, and this new concatenated string becomes the final
        ``rich_value`` for the whole column.

        If all :py:attr:`.sources` are ``None``, :py:attr:`.empty_value` will be used as the
        ``rich_value``.
        """

        values = []
        for source in self.sources:
            result = self.get_source_value(obj, source, **kwargs)

            for value in result:
                if isinstance(value, Model):
                    value = (value.pk, value)

                if value is not None:
                    if not isinstance(value, (tuple, list)):
                        value = (value, value)
                    values.append(value)

        if len(values) == 1:
            value = values[0]
            if value is None and self.empty_value is not None:
                value = self.empty_value
        elif len(values) > 0:
            plain_value = [v[0] for v in values]
            rich_value = self.separator.join(map(str, [v[1] for v in values]))
            value = (plain_value, rich_value)
        else:
            value = self.empty_value

        return value

    def get_source_value(self, obj, source, **kwargs):
        """
        Retrieves the value from ``obj`` associated with some ``source`` description.  Should return
        a list whose length is determined by the number of sources consulted.  In the default case,
        this is always just 1, but compound columns that declare their components with nested
        ``Column`` instances will have sources of their own and need to return a value per nested
        source.
        """
        if hasattr(source, "__call__"):
            value = source(obj)
        elif isinstance(obj, Model):
            value = reduce(get_attribute_value, [obj] + source.split("__"))
        elif isinstance(obj, dict):  # ValuesQuerySet item
            value = obj[source]
        else:
            raise ValueError("Unknown object type %r" % (repr(obj),))
        return [value]

    def get_processor_kwargs(self, **extra_kwargs):
        """
        Returns a dictionary of kwargs that should be sent to this column's :py:attr:`processor`
        callback.
        """
        kwargs = {
            "localize": self.localize,
        }
        kwargs.update(extra_kwargs)
        return kwargs

    def get_db_sources(self, model):
        """
        Returns the list of sources that match fields on the given ``model`` class.
        """
        sources = []
        for source in self.sources:
            target_field = self.resolve_source(model, source)
            if target_field:
                sources.append(source)
        return sources

    def get_virtual_sources(self, model):
        """
        Returns the list of sources that do not match fields on the given ``model`` class.
        """
        sources = []
        for source in self.sources:
            target_field = self.resolve_source(model, source)
            if target_field is None:
                sources.append(source)
        return sources

    def get_sort_fields(self, model):
        """
        Returns the list of sources that match fields on the given ``model`` class.  This will be
        the list of database-backed fields.
        """
        return self.get_db_sources(model)

    def expand_source(self, source):
        return (source,)

    def resolve_source(self, model, source):
        # Try to fetch the leaf attribute.  If this fails, the attribute is not database-backed and
        # the search for the first non-database field should end.
        if hasattr(source, "__call__"):
            return None
        try:
            return resolve_orm_path(model, source)
        except FieldDoesNotExist:
            return None

    def get_source_handler(self, model, source):
        """Return handler instance for lookup types and term coercion."""
        return self

    # Interactivity features
    def prep_search_value(self, term, lookup_type):
        """
        Coerce the input term to work for the given lookup_type.  Returns the coerced term, or
        ``None`` if the term and lookup_type are incompatible together.
        """

        # We avoid making changes that the Django ORM can already do for us
        multi_terms = None

        if isinstance(term, str):
            if lookup_type == "in":
                in_bits = re.split(r",\s*", term)
                if len(in_bits) > 1:
                    multi_terms = in_bits
                else:
                    term = None

            if lookup_type == "range":
                range_bits = re.split(r"\s*-\s*", term)
                if len(range_bits) == 2:
                    multi_terms = range_bits
                else:
                    term = None

        if multi_terms:
            return filter(
                None,
                (self.prep_search_value(multi_term, lookup_type) for multi_term in multi_terms),
            )

        model_field = self.model_field_class()
        try:
            term = model_field.get_prep_value(term)
        except Exception as err:
            log.info(f"model_field.get_prep_value({term}) - {err}")
            term = None

        return term

    def get_lookup_types(self, handler=None):
        """
        Generates the list of valid ORM lookup operators, taking into account runtime options for
        the ``allow_regex`` and ``allow_full_text_search`` options.
        """
        lookup_types = self.lookup_types
        if handler:
            lookup_types = handler.lookup_types

        # Add regex and MySQL 'search' operators if requested for the original column definition
        if self.allow_regex and "iregex" not in lookup_types:
            lookup_types += ("iregex",)
        if self.allow_full_text_search and "search" not in lookup_types:
            lookup_types += ("search",)
        return lookup_types

    def search(self, model, term, lookup_types=None):
        """
        Returns the ``Q`` object representing queries to make against this column for the given
        term.

        It is the responsibility of this method to decide which of this column's sources are
        database-backed and which are names of instance attributes, properties, or methods.  The
        ``model`` is provided to identify Django ORM ``ModelField`` s and related models.

        The default implementation resolves each contributing ``source`` from :py:attr:`sources`,
        and uses :py:meth:`.prep_search_value` to coerce the input search ``term`` to something
        usable for each of the query :py:attr:`lookup_types` supported by the column.  Any failed
        coercions will be skipped.

        The default implementation will also discover terms that match the source field's
        ``choices`` labels, flipping the term to automatically query for the internal choice value.
        """
        sources = self.get_db_sources(model)
        column_queries = []
        for source in sources:
            handler = self.get_source_handler(model, source)

            for sub_source in self.expand_source(source):
                modelfield = resolve_orm_path(model, sub_source)
                if hasattr(modelfield, "choices") and modelfield.choices:
                    if hasattr(modelfield, "get_choices"):
                        choices = modelfield.get_choices()
                    else:
                        choices = modelfield.get_flatchoices()
                    for db_value, label in choices:
                        if term.lower() in label.lower():
                            k = "%s__exact" % (sub_source,)
                            column_queries.append(Q(**{k: str(db_value)}))

                if not lookup_types:
                    lookup_types = handler.get_lookup_types()
                for lookup_type in lookup_types:
                    coerced_term = handler.prep_search_value(term, lookup_type)
                    if coerced_term is None:
                        # Skip terms that don't work with the lookup_type
                        continue
                    elif lookup_type in ("in", "range") and not isinstance(coerced_term, tuple):
                        # Skip attempts to build multi-component searches if we only have one term
                        continue

                    k = "%s__%s" % (sub_source, lookup_type)
                    column_queries.append(Q(**{k: coerced_term}))

        if column_queries:
            q = reduce(operator.or_, column_queries)
        else:
            q = None
        return q

    # Template rendering
    def __str__(self):
        """
        Renders a simple ``<th>`` element with ``data-name`` attribute.  All items found in the
        ``self.attributes`` dict are also added as dom attributes.
        """
        return mark_safe(
            """<th data-name="{name_slug}"{attrs}>{label}</th>""".format(
                **{
                    "name_slug": slugify(self.label),
                    "attrs": self.attributes,
                    "label": self.label,
                }
            )
        )

    @property
    def attributes(self):
        """
        Returns a dictionary of initial state data for sorting, sort direction, and visibility.

        The default attributes include ``data-config-sortable``, ``data-config-visible``, and (if
        applicable) ``data-config-sorting`` to hold information about the initial sorting state.
        """
        attributes = {
            "data-config-sortable": "true" if self.sortable else "false",
            "data-config-visible": "true" if self.visible else "false",
        }

        if self.sort_priority is not None:
            attributes["data-config-sorting"] = ",".join(
                map(
                    str,
                    [
                        self.sort_priority,
                        self.index,
                        self.sort_direction,
                    ],
                )
            )

        return flatatt(attributes)


class TextColumn(Column):
    model_field_class = models.CharField
    handles_field_classes = [
        models.CharField,
        models.TextField,
        models.FileField,
        models.GenericIPAddressField,
    ]

    # Add UUIDField if present in this version of Django
    try:
        handles_field_classes.append(models.UUIDField)
    except AttributeError:
        pass

    lookup_types = ("icontains", "in")


class DateColumn(Column):
    model_field_class = models.DateField
    handles_field_classes = [models.DateField]
    lookup_types = ("exact", "in", "range", "year", "month", "day", "week_day")

    def prep_search_value(self, term, lookup_type):
        if lookup_type in ("exact", "in", "range"):
            try:
                date_obj = dateutil.parser.parse(term)
            except ValueError:
                # This exception is theoretical, but it doesn't seem to raise.
                pass
            except TypeError:
                # Failed conversions can lead to the parser adding ints to None.
                pass
            else:
                return date_obj

        if lookup_type not in ("exact", "in", "range"):
            test_term = term
            if lookup_type == "week_day":
                try:
                    test_term = int(test_term) - 1  # Django ORM uses 1-7, python strptime uses 0-6
                except Exception as err:
                    log.info(f"int({test_term}) - 1 -- {err}")
                    return None
                else:
                    test_term = str(test_term)

            for test_format in STRPTIME_PLACEHOLDERS[lookup_type]:
                # Try to validate the term against the given date lookup type
                try:
                    date_obj = datetime.strptime(test_term, test_format)
                except ValueError:
                    pass
                else:
                    if lookup_type == "week_day":
                        term = (
                            date_obj.weekday() + 1
                        )  # Django ORM uses 1-7, python strptime uses 0-6
                    else:
                        term = getattr(date_obj, lookup_type)
                    return str(term)

        # At this point we have garbage..
        return None


class DateTimeColumn(DateColumn):
    model_field_class = models.DateTimeField
    handles_field_classes = [models.DateTimeField]
    lookup_types = (
        "exact",
        "in",
        "range",
        "year",
        "month",
        "day",
        "week_day",
        "hour",
        "minute",
        "second",
    )


class TimeColumn(DateColumn):
    model_field_class = models.TimeField
    handles_field_classes = [models.TimeField]
    lookup_types = ("exact", "in", "range", "hour", "minute", "second")


class BooleanColumn(Column):
    model_field_class = models.BooleanField
    handles_field_classes = [models.BooleanField, models.NullBooleanField]
    lookup_types = ("exact", "in")

    def prep_search_value(self, term, lookup_type):
        try:
            term = term.lower()
        except AttributeError:
            pass

        # In some cases self.label is None
        try:
            label = self.label.lower()
        except AttributeError:
            label = ""

        # Allow column's own label to represent a true value
        if term in ["True", "true"] or term in label:
            term = True
        elif term in ["False", "false"]:
            term = False
        else:
            return None

        return super(BooleanColumn, self).prep_search_value(term, lookup_type)


class IntegerColumn(Column):
    model_field_class = models.IntegerField
    handles_field_classes = [models.IntegerField, models.AutoField]
    lookup_types = ("exact", "in")


class FloatColumn(Column):
    model_field_class = models.FloatField
    handles_field_classes = [models.FloatField, models.DecimalField]
    lookup_types = ("exact", "in")


class CompoundColumn(Column):
    """
    Special column type for holding multiple sources that have different model field types.  The
    separation of sources by type is important because of the different query lookup types that are
    allowed against different model fields.

    Each source will dynamically find its associated model field and choose an appropriate column
    class from the registry.

    To more finely control which column class is used, an actual column instance can be given
    instead of a string name which declares its own ``source`` or ``sources``.  Because they are not
    important to the client-side representation of the column, no ``label`` is necessary for nested
    column instances.
    """

    model_field_class = None
    handles_field_classes = []
    lookup_types = ()

    def expand_source(self, source):
        if isinstance(source, Column):
            return source.sources
        return super(CompoundColumn, self).expand_source(source)

    def get_source_value(self, obj, source, **kwargs):
        """
        Treat ``field`` as a nested sub-Column instance, which explicitly stands in as the object
        to which term coercions and the query type lookup are delegated.
        """
        result = []
        for sub_source in self.expand_source(source):
            # Call super() to get default logic, but send it the 'sub_source'
            sub_result = super(CompoundColumn, self).get_source_value(obj, sub_source, **kwargs)
            result.extend(sub_result)
        return result

    def get_db_sources(self, model):
        return self.sources

    def get_sort_fields(self, model):
        return self._get_flat_db_sources(model)

    def _get_flat_db_sources(self, model):
        """Return a flattened representation of the individual ``sources`` lists."""
        sources = []
        for source in self.sources:
            for sub_source in self.expand_source(source):
                target_field = self.resolve_source(model, sub_source)
                if target_field:
                    sources.append(sub_source)
        return sources

    def get_source_handler(self, model, source):
        """Allow the nested Column source to be its own handler."""
        if isinstance(source, Column):
            return source

        # Generate a generic handler for the source
        modelfield = resolve_orm_path(model, source)
        column_class = get_column_for_modelfield(modelfield)
        return column_class()


class DisplayColumn(Column):
    """
    Convenience column type for unsearchable, unsortable columns, which rely solely on a processor
    function to generate content.
    """

    model_field_class = None
    lookup_types = ()


class CheckBoxSelectColumn(DisplayColumn):
    """
    Renders a column of checkboxes with Select all items checkbox on the top
    Example here: https://datatables.net/extensions/select/examples/initialisation/checkbox.html
    """

    def __init__(self, label="Select all", show_select_checkbox=True, *args, **kwargs):
        if show_select_checkbox:
            label += """
                <input
                data-id='all'
                type='checkbox'
                onchange="
                if ($(this).is(':checked')) {
                $(this).closest('table').DataTable().rows().select();
                } else {
                $(this).closest('table').DataTable().rows().deselect();
                }
                ">
                """
        super(CheckBoxSelectColumn, self).__init__(label=label, *args, **kwargs)

    def value(self, obj, **kwargs):
        return ""
