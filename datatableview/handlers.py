# -*- encoding: utf-8 -*-

import datetime
import dateutil.parser

__all__ = (
    'boolean_field_handler', 'date_field_handler', 'float_field_handler', 'ignored_field_handler',
    'integer_field_handler', 'text_field_handler'
)


def boolean_field_handler(field, component_name, term):
    if term.lower() in ('true', 'yes'):
        return [{component_name: True}]
    elif term.lower() in ('false', 'no'):
        return [{component_name: False}]


def date_field_handler(field, component_name, term):
    field_queries = []
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

    return field_queries


def float_field_handler(field, component_name, term):
    try:
        return [{component_name: float(term)}]
    except ValueError:
        pass


def ignored_field_handler(field, component_name, term):
    pass


def integer_field_handler(field, component_name, term):
    try:
        return [{component_name: int(term)}]
    except ValueError:
        pass


def text_field_handler(field, component_name, term):
    return [{component_name + '__icontains': term}]
