# coding=utf-8
"""
A collection of small helper functions for generating small pieces of datatable output in custom
methods on a view.

Because of uncontrolled external use of ``preload_record_data()`` by the view, each of these utility
functions allows for generic ``*args`` to pass through to the function, even though they aren't used
in any way.

"""

from django import get_version

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

    def wrapper(instance=None, key=None, *args, **kwargs):
        if instance is not None and not key:
            value = instance
            return helper(value, *args, **kwargs)
        elif instance is None:
            if key:
                # Helper is used directly in the columns declaration.  A new callable is
                # returned to take the place of a callback.
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
        text = kwargs.get('default_value') or unicode(instance)
    return u"""<a href="{}">{}</a>""".format(instance.get_absolute_url(), text)


@keyed_helper
def make_boolean_checkmark(value, true_value="&#10004;", false_value="&#10008;", *args, **kwargs):
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
        if ellipsis and isinstance(k, slice) and isinstance(value, basestring) and \
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



def format_date(format_string, key=None, localize=False):
    if localize is not False and localtime is None:
        raise Exception("Cannot use format_date argument 'localized' with Django < 1.5")
    def helper(value, *args, **kwargs):
        if key:
            value = key(value)
        if localize:
            value = localtime(value)
        try:
            return value.strftime(format_string)
        except AttributeError:
            return ""

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
