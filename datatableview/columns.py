import re
try:
    from functools import reduce
except ImportError:
    pass

from django.db import models
from django.db.models import Model, Manager
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_text

import six

from .utils import DEFAULT_EMPTY_VALUE, DEFAULT_MULTIPLE_SEPARATOR

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

# Corollary to django.forms.fields.Field
class Column(object):
    """ Generic table column using CharField for rendering. """

    model_field_class = models.CharField
    widget_class = None

    # Tracks each time a Field instance is created. Used to retain order.
    creation_counter = 0

    def __init__(self, label=None, sources=None, model_field_class=None,
                 separator=DEFAULT_MULTIPLE_SEPARATOR, empty_value=DEFAULT_EMPTY_VALUE,
                 localize=False, processor=None):
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
        self.processor = processor

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
            value = reduce(get_attribute_value, [obj] + field_name.split('__'))

            if isinstance(value, Model):
                value = six.text_type(value)

            if value is not None:
                values.append(value)

        if len(values) == 1:
            value = values[0]
            if value is None and self.empty_value is not None:
                value = self.empty_value
        elif len(values) > 0:
            value = self.separator.join(map(six.text_type, values))
        else:
            value = self.empty_value

        # if 'datatable' in kwargs:
        #     return kwargs['datatable'].process_value(obj, default_value=value, **kwargs)

        return value
        

    def get_processor_kwargs(self, **kwargs):
        return kwargs


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
