# -*- coding: utf-8 -*-

from functools import reduce

from django.utils.text import smart_split

MINIMUM_PAGE_LENGTH = 1
DEFAULT_EMPTY_VALUE = ""
DEFAULT_MULTIPLE_SEPARATOR = " "

# Since it's rather painful to deal with the datatables.js naming scheme in Python, this map changes
# the Pythonic names to the javascript ones in the GET request
OPTION_NAME_MAP = {
    "start_offset": "start",
    "page_length": "length",
    "search": "search[value]",
    "search_column": "columns[%d][search][value]",
    "sort_column": "order[%d][column]",
    "sort_column_direction": "order[%d][dir]",
}

# Mapping of Django's supported field types to their more generic type names.
# These values are primarily used for the xeditable field type lookups.
# TODO: Would be nice if we can derive these from FIELD_TYPES so there's less repetition.
XEDITABLE_FIELD_TYPES = {
    "AutoField": "number",
    "BooleanField": "text",
    "CharField": "text",
    "CommaSeparatedIntegerField": "text",
    "DateField": "date",
    "DateTimeField": "datetime",
    "DecimalField": "text",
    "FileField": "text",
    "FilePathField": "text",
    "FloatField": "number",
    "IntegerField": "number",
    "BigIntegerField": "number",
    "IPAddressField": "text",
    "GenericIPAddressField": "text",
    "NullBooleanField": "text",
    "PositiveIntegerField": "number",
    "PositiveSmallIntegerField": "number",
    "SlugField": "text",
    "SmallIntegerField": "number",
    "TextField": "text",
    "TimeField": "text",
    "ForeignKey": "select",
}


def resolve_orm_path(model, orm_path):
    """
    Follows the queryset-style query path of ``orm_path`` starting from ``model`` class.  If the
    path ends up referring to a bad field name, ``django.db.models.fields.FieldDoesNotExist`` will
    be raised.

    """

    bits = orm_path.split("__")
    endpoint_model = reduce(get_model_at_related_field, [model] + bits[:-1])
    if bits[-1] == "pk":
        field = endpoint_model._meta.pk
    else:
        field = endpoint_model._meta.get_field(bits[-1])
    return field


def get_model_at_related_field(model, attr):
    """
    Looks up ``attr`` as a field of ``model`` and returns the related model class.  If ``attr`` is
    not a relationship field, ``ValueError`` is raised.

    """

    field = model._meta.get_field(attr)

    if hasattr(field, "related_model"):
        return field.related_model

    raise ValueError(
        "{model}.{attr} ({klass}) is not a relationship field.".format(
            **{
                "model": model.__name__,
                "attr": attr,
                "klass": field.__class__.__name__,
            }
        )
    )


def get_first_orm_bit(column):
    """Returns the first ORM path component of a field definition's declared db field."""
    if not column.sources:
        return None

    return column.sources[0].split("__")[0]


def contains_plural_field(model, fields):
    """Returns a boolean indicating if ``fields`` contains a relationship to multiple items."""
    source_model = model
    for orm_path in fields:
        model = source_model
        bits = orm_path.lstrip("+-").split("__")
        for bit in bits[:-1]:
            field = model._meta.get_field(bit)
            if field.many_to_many or field.one_to_many:
                return True
            model = get_model_at_related_field(model, bit)
    return False


def split_terms(s):
    return filter(None, map(lambda t: t.strip("'\" "), smart_split(s)))
