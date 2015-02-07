import re
import operator
from collections import defaultdict
try:
    from functools import reduce
except ImportError:
    pass

from django import get_version
from django.db import models
from django.db.models import Model, Manager, Q
from django.db.models.fields import FieldDoesNotExist
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_text
from django.utils.safestring import mark_safe
from django.forms.util import flatatt
from django.template.defaultfilters import slugify
try:
    from django.utils.encoding import python_2_unicode_compatible
except ImportError:
    from .compat import python_2_unicode_compatible

import six
import dateutil

from .utils import resolve_orm_path, DEFAULT_EMPTY_VALUE, DEFAULT_MULTIPLE_SEPARATOR

# Registry of Column subclasses to their declared corresponding ModelField.
# There are manual additions to this setting after the column definitions below.
COLUMN_CLASSES = defaultdict(list)


def get_attribute_value(obj, bit):
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

class ColumnMetaclass(type):
    """ Column type for automatic registration of column types as ModelField handlers. """
    def __new__(cls, name, bases, attrs):
        new_class = super(ColumnMetaclass, cls).__new__(cls, name, bases, attrs)
        COLUMN_CLASSES[new_class].append(new_class.model_field_class)
        return new_class


# Corollary to django.forms.fields.Field
@python_2_unicode_compatible
class Column(six.with_metaclass(ColumnMetaclass)):
    """ Generic table column using CharField for rendering. """

    model_field_class = models.CharField

    lookup_types = ('exact', 'in')

    # Tracks each time a Field instance is created. Used to retain order.
    creation_counter = 0

    def __init__(self, label=None, sources=None, model_field_class=None,
                 separator=DEFAULT_MULTIPLE_SEPARATOR, empty_value=DEFAULT_EMPTY_VALUE,
                 sortable=True, visible=True, localize=False, processor=None, allow_regex=False,
                 allow_full_text_search=False):
        if model_field_class:
            self.model_field_class = model_field_class

        self.name = None  # Set outside, once the Datatable can put it there
        if label is not None:
            label = smart_text(label)
        self.sources = sources or []  # TODO: Process for real/virtual
        if not isinstance(self.sources, (tuple, list)):
            self.sources = [self.sources]
        self.separator = separator
        self.label = label
        self.empty_value = smart_text(empty_value)
        self.localize = localize
        self.sortable = sortable
        self.visible = visible
        self.processor = processor
        self.allow_regex = allow_regex
        self.allow_full_text_search = allow_full_text_search

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
        Returns the 2-tuple of (rich_value, plain_value) for the inspection and serialization phases
        of serialization.
        """

        kwargs = self.get_processor_kwargs(**kwargs)
        values = self.process_value(obj, **kwargs)

        if not isinstance(values, (tuple, list)):
            values = (values, values)

        return values

    def process_value(self, obj, **kwargs):
        """ Default value processor for the target data source. """

        values = []
        for field_name in self.sources:
            if isinstance(obj, Model):
                value = reduce(get_attribute_value, [obj] + field_name.split('__'))
            else:
                value = obj[field_name]

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
            rich_value = self.separator.join(map(six.text_type, [v[1] for v in values]))
            value = (plain_value, rich_value)
        else:
            value = self.empty_value

        return value
        

    def get_processor_kwargs(self, **kwargs):
        return kwargs

    def get_db_sources(self, model):
        sources = []
        for source in self.sources:
            target_field = self._resolve_source(model, source)
            if target_field:
                sources.append(source)
        return sources

    def get_virtual_sources(self, model):
        sources = []
        for source in self.sources:
            target_field = self._resolve_source(model, source)
            if target_field is None:
                sources.append(source)
        return sources

    def _resolve_source(self, model, source):
        # Try to fetch the leaf attribute.  If this fails, the attribute is not database-backed and
        # the search for the first non-database field should end.
        try:
            return resolve_orm_path(model, source)
        except FieldDoesNotExist:
            return None

    # Interactivity features
    def get_column_for_source(self, model, source):
        """ Generates a temporary searchterm-handling Column for a given ``source``. """
        # TODO: Get this method on the Datatable instead of the Column
        modelfield = resolve_orm_path(model, source)
        for Column, modelfields in COLUMN_CLASSES.items():
            if isinstance(modelfield, tuple(modelfields)):
                return Column()

    def prep_search_value(self, term, lookup_type):
        """ Coerce the input term to work for the given lookup_type. """

        # We avoid making changes that the Django ORM can already do for us
        multi_terms = None

        if lookup_type == "in":
            in_bits = re.split(r',\s*', term)
            if len(in_bits) > 1:
                multi_terms = in_bits
            else:
                term = None

        if lookup_type == "range":
            range_bits = re.split(r'\s*-\s*', term)
            if len(range_bits) == 2:
                multi_terms = range_bits
            else:
                term = None

        if multi_terms:
            return filter(None, (self.prep_search_value(multi_term) for multi_term in multi_terms))

        if lookup_type not in ('year', 'month', 'day', 'hour' 'minute', 'second', 'week_day'):
            model_field = self.model_field_class()
            try:
                term = model_field.get_prep_value(term)
            except:
                term = None
        else:
            try:
                term = int(term)
            except ValueError:
                term = None

        return term

    def get_lookup_types(self, handler=None):
        """ Generates the list of valid ORM lookup operators. """
        lookup_types = self.lookup_types
        if handler:
            lookup_types = handler.lookup_types

        # Add regex and MySQL 'search' operators if requested for the original column definition
        if self.allow_regex and 'iregex' not in lookup_types:
            lookup_types += ('iregex',)
        if self.allow_full_text_search and 'search' not in lookup_types:
            lookup_types += ('search',)
        return lookup_types

    def search(self, model, terms):
        """
        Returns the ``Q`` object representing queries made against this column for the given terms.
        """
        sources = self.get_db_sources(model)
        column_queries = []
        for term in terms:
            term_queries = []
            for source in sources:
                handler = self.get_column_for_source(model, source)
                lookup_types = self.get_lookup_types(handler=handler)
                for lookup_type in lookup_types:
                    coerced_term = (handler or self).prep_search_value(term, lookup_type)
                    if coerced_term is None:
                        # Skip terms that don't work with the lookup_type
                        continue
                    elif lookup_type in ('in', 'range') and not isinstance(coerced_term, tuple):
                        # Skip attempts to build multi-component searches if we only have one term
                        continue

                    k = '%s__%s' % (source, lookup_type)
                    term_queries.append(Q(**{k: coerced_term}))

            if term_queries:
                q = reduce(operator.or_, term_queries)
                column_queries.append(q)

        if column_queries:
            q = reduce(operator.or_, term_queries)
        else:
            q = None
        return q

    def get_sort_fields(self):
        return self.get_db_sources()

    # Template rendering
    def __str__(self):
        return mark_safe(u"""<th data-name="{name_slug}"{attrs}>{label}</th>""".format(**{
            'name_slug': slugify(self.label),
            'attrs': self.attributes,
            'label': self.label,
        }))

    @property
    def attributes(self):
        attributes = {
            'data-sortable': 'true' if self.sortable else 'false',
            'data-visible': 'true' if self.visible else 'false',
        }

        if self.sort_priority is not None:
            attributes['data-sorting'] = ','.join(map(six.text_type, [
                self.sort_priority,
                self.index,
                self.sort_direction,
            ]))

        return flatatt(attributes)


class TextColumn(Column):
    model_field_class = models.CharField
    lookup_types = ('iexact', 'in', 'icontains')


class DateColumn(Column):
    model_field_class = models.DateField
    lookup_types = ('exact', 'in', 'range', 'year', 'month', 'day', 'week_day')

    def prep_search_value(self, term, lookup_type):
        if lookup_type in ('exact', 'in', 'range'):
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
        return super(DateColumn, self).prep_search_value(term, lookup_type)


class DateTimeColumn(DateColumn):
    model_field_class = models.DateTimeField
    lookups_types = ('exact', 'in', 'range', 'year', 'month', 'day', 'week_day')


if get_version().split('.') >= ['1', '6']:
    DateTimeColumn.lookup_types += ('hour', 'minute', 'second')


class BooleanColumn(Column):
    model_field_class = models.BooleanField


class IntegerColumn(Column):
    model_field_class = models.IntegerField


class FloatColumn(Column):
    model_field_class = models.FloatField


class ForeignKeyColumn(Column):
    model_field_class = models.ForeignKey


# Modifications to built-in column mapping
COLUMN_CLASSES[IntegerColumn].append(models.AutoField)
