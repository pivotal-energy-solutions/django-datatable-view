# -*- encoding: utf-8 -*-

"""
A collection of small helper functions for generating small pieces of datatable output in custom
methods on a view.

Because of uncontrolled external use of ``preload_record_data()`` by the view, each of these utility
functions allows for generic ``*args`` to pass through to the function, even though they aren't used
in any way.

"""

from functools import partial, wraps

from django import get_version
try:
    from django.forms.utils import flatatt
except ImportError:
    from django.forms.util import flatatt

import six

from .utils import resolve_orm_path, XEDITABLE_FIELD_TYPES

if get_version().split('.') >= ['1', '5']:
    from django.utils.timezone import localtime
else:
    localtime = None


def keyed_helper(helper):
    """
    Decorator for helper functions that operate on direct values instead of model instances.

    A keyed helper is one that can be used normally in the view's own custom callbacks, but also
    supports direct access in the column declaration, such as in the example:

        datatable_options = {
            'columns': [
                ('Field Name', 'fieldname', make_boolean_checkmark(key=attrgetter('fieldname'))),
            ],
        }

    With the help of a ``sort``-style ``key`` argument, the helper can receive all the information
    it requires in advance, so that the view doesn't have to go through the trouble of declaring
    a custom callback method that simply returns the value of the ``make_boolean_checkmark()``
    helper.

    If the attribute being fetched is identical to the one pointed to in the column declaration,
    even the ``key`` argument can be omitted:

        ('Field Name', 'fieldname', make_boolean_checkmark)),

    """

    @wraps(helper)
    def wrapper(instance=None, key=None, *args, **kwargs):
        if instance is not None and not key:
            return helper(instance, *args, **kwargs)
        elif instance is None:
            if key:
                # Helper is used directly in the columns declaration.  A new callable is
                # returned to take the place of a callback.
                @wraps(helper)
                def helper_wrapper(instance, *args, **kwargs):
                    return helper(key(instance), *args, **kwargs)
                return helper_wrapper
            else:
                # helper was called in place with neither important arg
                raise ValueError("If called directly, helper function '%s' requires either a model"
                                 " instance or a 'key' keyword argument." % helper.__name__)
    wrapper._is_wrapped = True
    return wrapper


@keyed_helper
def link_to_model(instance, text=None, *args, **kwargs):
    """
    Returns HTML in the form

        <a href="{{ instance.get_absolute_url }}">{{ instance }}</a>

    If ``text`` is provided and is true-like, it will be used as the hyperlinked text.

    Else, if ``kwargs['default_value']`` is available, it will be consulted.

    Failing those checks, ``unicode(instance)`` will be inserted as the hyperlinked text.

    """
    if not text:
        text = kwargs.get('default_value') or six.text_type(instance)
    return u"""<a href="{0}">{1}</a>""".format(instance.get_absolute_url(), text)


@keyed_helper
def field_display(instance, *args, **kwargs):
    """
    Returns the display name of a field
    """
    field_name = kwargs.get('field_data')[1]
    field_display_method_name = 'get_' + field_name + '_display'
    method = getattr(instance, field_display_method_name)
    return u"{}".format(method())


@keyed_helper
def make_boolean_checkmark(value, true_value="&#10004;", false_value="&#10008;", *args, **kwargs):
    value = kwargs.get('default_value', value)
    if value:
        return true_value
    return false_value


def itemgetter(k, ellipsis=False, key=None):
    """
    Looks up ``k`` as an index to the target value.  If ``ellipsis`` is given and k is a ``slice``
    type object, then ``ellipsis`` can be a string to use to indicate a truncation, or simply
    ``True`` to use a default ``"..."``.  If a ``key`` is given, it may be a function which maps the
    target value to something else before the item lookup takes place.
    """
    def helper(instance, *args, **kwargs):
        default_value = kwargs.get('default_value')
        if default_value is None:
            default_value = instance
        value = default_value[k]
        if ellipsis and isinstance(k, slice) and isinstance(value, six.string_types) and \
                len(default_value) > len(value):
            if ellipsis is True:
                value += "..."
            else:
                value += ellipsis
        return value

    if key:
        helper = keyed_helper(helper)(key=key)
    return helper


def attrgetter(attr, key=None):
    """
    Looks up ``attr`` on the target value, and tries to call it if the value is callable.  If a
    ``key`` is given, it may be a function which maps the target value to something else before the
    attribute lookup takes place.
    """
    def helper(instance, *args, **kwargs):
        value = instance
        for bit in attr.split('.'):
            value = getattr(value, bit)
            if callable(value):
                value = value()
        return value

    if key:
        helper = keyed_helper(helper)(key=key)
    return helper


def format_date(format_string, localize=False, key=None):
    if localize is not False and localtime is None:
        raise Exception("Cannot use format_date argument 'localize' with Django < 1.5")

    def helper(value, *args, **kwargs):
        if key:
            value = key(value)
        else:
            value = kwargs.get('default_value', value)
        if not value:  # Empty or missing default_value
            return ""
        if localize:
            value = localtime(value)
        return value.strftime(format_string)

    if key:
        return keyed_helper(helper)(key=key)
    return helper


def format(format_string, cast=lambda x: x):
    def helper(instance, *args, **kwargs):
        value = kwargs.get('default_value')
        if value is None:
            value = instance
        value = cast(value)
        return format_string.format(value, obj=instance)
    return helper


def make_xeditable(instance=None, extra_attrs=[], *args, **kwargs):
    if instance is None:
        # Preloading kwargs into the helper for deferred execution
        helper = partial(make_xeditable, extra_attrs=extra_attrs, *args, **kwargs)
        return helper

    # Immediate finalization, return the xeditable structure
    data = kwargs.get('default_value', instance)

    # Compile values to appear as "data-*" attributes on the anchor tag
    default_attr_names = ['pk', 'type', 'url', 'source', 'title', 'placeholder']
    valid_attr_names = set(default_attr_names + list(extra_attrs))
    attrs = {}
    for k, v in kwargs.items():
        if k in valid_attr_names:
            if k.startswith('data_'):
                k = k[5:]
            attrs['data-{0}'.format(k)] = v

    attrs['data-xeditable'] = "xeditable"

    # Assign default values where they are not provided

    field_name = kwargs['field_data']  # sent as a default kwarg to helpers
    if isinstance(field_name, (tuple, list)):
        field_name = field_name[1]
        if isinstance(field_name, (tuple, list)):
            raise ValueError("'make_xeditable' helper needs a single-field data column,"
                             " not {0!r}".format(field_name))
    attrs['data-name'] = field_name
    attrs['data-value'] = data

    if 'data-pk' not in attrs:
        attrs['data-pk'] = instance.pk

    if 'data-url' not in attrs:
        # Look for a backup data-url
        provider_name = 'get_update_url'
        url_provider = getattr(kwargs.get('view'), provider_name, None)
        if not url_provider:
            url_provider = getattr(instance, provider_name, None)
            if not url_provider and 'view' in kwargs:
                url_provider = lambda field_name: kwargs['view'].request.path
            else:
                raise ValueError("'make_xeditable' cannot determine a value for 'url'.")
        if url_provider:
            attrs['data-url'] = url_provider(field_name=field_name)

    if 'data-placeholder' not in attrs:
        attrs['data-placeholder'] = attrs.get('data-title', "")

    if 'data-type' not in attrs:
        if hasattr(instance, '_meta'):
            # Try to fetch a reasonable type from the field's class
            if field_name == 'pk':  # special field name not in Model._meta.fields
                field = instance._meta.pk
            else:
                field = resolve_orm_path(instance, field_name)

            if field.choices:
                field_type = 'select'
            else:
                field_type = XEDITABLE_FIELD_TYPES.get(field.get_internal_type(), 'text')
        else:
            field_type = 'text'
        attrs['data-type'] = field_type

    # type=select elements need to fetch their valid choice options from an AJAX endpoint.
    # Register the view for this lookup.
    if attrs['data-type'] in ('select', 'select2'):
        if 'data-source' not in attrs:
            if 'view' in kwargs:
                attrs['data-source'] = "{url}?{field_param}={fieldname}".format(**{
                    'url': kwargs['view'].request.path,
                    'field_param': kwargs['view'].xeditable_fieldname_param,
                    'fieldname': field_name,
                })
                if attrs['data-type'] == 'select2':
                    attrs['data-source'] += '&select2=true'
            else:
                raise ValueError("'make_xeditable' cannot determine a value for 'source'.")

        # Choice fields will want to display their readable label instead of db data
        data = getattr(instance, 'get_{0}_display'.format(field_name), lambda: data)()

    data = u"""<a href="#"{attrs}>{data}</a>""".format(attrs=flatatt(attrs), data=data)
    return data


def through_filter(template_filter, arg=None):
    def helper(instance, *args, **kwargs):
        value = kwargs.get('default_value')
        if value is None:
            value = instance
        if arg is not None:
            extra_arg = [arg]
        else:
            extra_arg = []
        return template_filter(value, *extra_arg)
    return helper
