import re
try:
    from functools import reduce
except ImportError:
    pass

from django.db import models
from django.db.models import Model, Manager
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
    widget_class = None

    # Tracks each time a Field instance is created. Used to retain order.
    creation_counter = 0

    def __init__(self, label=None, sources=None, model_field_class=None,
                 separator=DEFAULT_MULTIPLE_SEPARATOR, empty_value=DEFAULT_EMPTY_VALUE,
                 sortable=True, visible=True, localize=False, processor=None):
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


class DateColumn(Column):
    model_field_class = models.DateField


class DateTimeColumn(Column):
    model_field_class = models.DateTimeField


class BooleanColumn(Column):
    model_field_class = models.BooleanField


class IntegerColumn(Column):
    model_field_class = models.IntegerField


class FloatColumn(Column):
    model_field_class = models.FloatField


class ForeignKeyColumn(Column):
    model_field_class = models.ForeignKey
