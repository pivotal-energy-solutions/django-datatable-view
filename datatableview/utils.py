# -*- encoding: utf-8 -*-

try:
    from functools import reduce
except ImportError:
    pass

from django.db import models
from django.db.models.fields import FieldDoesNotExist
from django.utils.text import smart_split
try:
    from django.db.models.related import RelatedObject
    USE_RELATED_OBJECT = True
except ImportError:
    from django.db.models.fields.related import RelatedField
    USE_RELATED_OBJECT = False

MINIMUM_PAGE_LENGTH = 1
DEFAULT_EMPTY_VALUE = ""
DEFAULT_MULTIPLE_SEPARATOR = u" "

# Since it's rather painful to deal with the datatables.js naming scheme in Python, this map changes
# the Pythonic names to the javascript ones in the GET request
OPTION_NAME_MAP = {
    'start_offset': 'iDisplayStart',
    'page_length': 'iDisplayLength',
    'search': 'sSearch',
    'search_column': 'sSearch_%d',
    'num_sorting_columns': 'iSortingCols',
    'sort_column': 'iSortCol_%d',
    'sort_column_direction': 'sSortDir_%d',
}

# Mapping of Django's supported field types to their more generic type names.
# These values are primarily used for the xeditable field type lookups.
# TODO: Would be nice if we can derive these from FIELD_TYPES so there's less repetition.
XEDITABLE_FIELD_TYPES = {
    'AutoField': 'number',
    'BooleanField': 'text',
    'CharField': 'text',
    'CommaSeparatedIntegerField': 'text',
    'DateField': 'date',
    'DateTimeField': 'datetime',
    'DecimalField': 'text',
    'FileField': 'text',
    'FilePathField': 'text',
    'FloatField': 'number',
    'IntegerField': 'number',
    'BigIntegerField': 'number',
    'IPAddressField': 'text',
    'GenericIPAddressField': 'text',
    'NullBooleanField': 'text',
    'PositiveIntegerField': 'number',
    'PositiveSmallIntegerField': 'number',
    'SlugField': 'text',
    'SmallIntegerField': 'number',
    'TextField': 'text',
    'TimeField': 'text',
    'ForeignKey': 'select',
}

def resolve_orm_path(model, orm_path):
    """
    Follows the queryset-style query path of ``orm_path`` starting from ``model`` class.  If the
    path ends up referring to a bad field name, ``django.db.models.fields.FieldDoesNotExist`` will
    be raised.

    """

    bits = orm_path.split('__')
    endpoint_model = reduce(get_model_at_related_field, [model] + bits[:-1])
    if bits[-1] == 'pk':
        field = endpoint_model._meta.pk
    else:
        field, _, _, _ = endpoint_model._meta.get_field_by_name(bits[-1])
    return field

def get_model_at_related_field(model, attr):
    """
    Looks up ``attr`` as a field of ``model`` and returns the related model class.  If ``attr`` is
    not a relationship field, ``ValueError`` is raised.

    """

    try:
        field, _, direct, m2m = model._meta.get_field_by_name(attr)
    except FieldDoesNotExist:
        raise

    if not direct:
        if hasattr(field, 'related_model'):  # Reverse relationship
            # -- Django >=1.8 mode
            return field.related_model
        elif hasattr(field, "model"):
            # -- Django <1.8 mode
            return field.model

    if hasattr(field, 'rel') and field.rel:  # Forward/m2m relationship
        return field.rel.to

    if hasattr(field, 'field'):  # Forward GenericForeignKey in Django 1.6+
        return field.field.rel.to

    raise ValueError("{0}.{1} ({2}) is not a relationship field.".format(model.__name__, attr,
                                                                         field.__class__.__name__))

def get_first_orm_bit(column):
    """ Returns the first ORM path component of a field definition's declared db field. """
    if not column.sources:
        return None

    return column.sources[0].split('__')[0]

def contains_plural_field(model, fields):
    """ Returns a boolean indicating if ``fields`` contains a relationship to multiple items. """
    source_model = model
    for orm_path in fields:
        model = source_model
        bits = orm_path.lstrip('+-').split('__')
        for bit in bits[:-1]:
            field, _, direct, m2m = model._meta.get_field_by_name(bit)
            if isinstance(field, models.ManyToManyField) \
                    or (USE_RELATED_OBJECT and isinstance(field, RelatedObject) and field.field.rel.multiple) \
                    or (not USE_RELATED_OBJECT and isinstance(field, RelatedField) and field.one_to_many):
                return True
            model = get_model_at_related_field(model, bit)
    return False

def split_terms(s):
    return filter(None, map(lambda t: t.strip("'\" "), smart_split(s)))

