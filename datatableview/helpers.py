# -*- coding: utf-8 -*-
"""
A collection of small helper functions for generating small pieces of datatable output in custom
methods on a view.

Because of uncontrolled external use of ``preload_record_data()`` by the view, each of these utility
functions allows for generic ``*args`` to pass through to the function, even though they aren't used
in any way.

"""

from functools import partial, wraps
import operator

from django.db.models import Model
from django.forms.utils import flatatt

from .utils import resolve_orm_path, XEDITABLE_FIELD_TYPES

from django.utils.timezone import localtime


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
    def wrapper(instance=None, key=None, attr=None, *args, **kwargs):
        if set((instance, key, attr)) == {None}:
            # helper was called in place with neither important arg
            raise ValueError(
                "If called directly, helper function '%s' requires either a model"
                " instance, or a 'key' or 'attr' keyword argument." % helper.__name__
            )

        if instance is not None:
            return helper(instance, *args, **kwargs)

        if key is None and attr is None:
            attr = "self"

        if attr:
            if attr == "self":
                key = lambda obj: obj  # noqa: E731
            else:
                key = operator.attrgetter(attr)

        # Helper is used directly in the columns declaration.  A new callable is
        # returned to take the place of a callback.
        @wraps(helper)
        def helper_wrapper(instance, *args, **kwargs):
            return helper(key(instance), *args, **kwargs)

        return helper_wrapper

    wrapper._is_wrapped = True
    return wrapper


@keyed_helper
def link_to_model(instance, text=None, *args, **kwargs):
    """
    Returns HTML in the form::

        <a href="{{ instance.get_absolute_url }}">{{ text }}</a>

    If ``text`` is provided and isn't empty, it will be used as the hyperlinked text.

    If ``text`` isn't available, then ``kwargs['rich_value']`` will be consulted instead.

    Failing those checks, the helper will fall back to simply using ``unicode(instance)`` as the
    link text.

    If the helper is called in place (rather than providing the helper reference directly), it can
    receive a special ``key`` argument, which is a mapping function that will receiving the instance
    (once it is available) and return some value from that instance.  That new value will be sent to
    the helper in the place of the instance.

    Examples::

        # Generate a simple href tag for instance.get_absolute_url()
        name = columns.TextColumn("Name", sources=['name'],
                                          processor=link_to_model)

        # Generate an href tag for instance.relatedobject.get_absolute_url()
        # Note that without the use of link_to_model(key=...), the object going into
        # the link_to_model helper would be the row instance, not the thing looked up by the
        # column's sources.
        name = columns.TextColumn("Name", sources=['relatedobject__name'],
                                          processor=link_to_model(key=getattr('relatedobject')))
    """
    if not text:
        text = kwargs.get("rich_value") or str(instance)
    return """<a href="{0}">{1}</a>""".format(instance.get_absolute_url(), text)


@keyed_helper
def make_boolean_checkmark(value, true_value="&#10004;", false_value="&#10008;", *args, **kwargs):
    """
    Returns a unicode ✔ or ✘, configurable by pre-calling the helper with ``true_value`` and/or
    ``false_value`` arguments, based on the incoming value.

    The value at ``kwargs['default_value']`` is checked to see if it casts to a boolean ``True`` or
    ``False``, and returns the appropriate representation.

    Examples::

        # A DateTimeField can be sent to the helper to detect whether
        # or not it is None, and have a checkmark reflect that.
        is_published = columns.DateTimeColumn("Published", sources=['published_date'],
                                              processor=make_boolean_checkmark)

        # Make the 'false_value' blank so that only True-like items have an icon
        is_published = columns.DateTimeColumn("Published", sources=['published_date'],
                                              processor=make_boolean_checkmark(false_value=""))

    """
    value = kwargs.get("default_value", value)
    if value:
        return true_value
    return false_value


def itemgetter(k, ellipsis=False, key=None):
    """
    Looks up ``k`` as an index of the column's value.

    If ``k`` is a ``slice`` type object, then ``ellipsis`` can be given as a string to use to
    indicate truncation.  Alternatively, ``ellipsis`` can be set to ``True`` to use a default
    ``'...'``.

    If a ``key`` is given, it may be a function which maps the target value to something else
    before the item lookup takes place.

    Examples::

        # Choose an item from a list source.
        winner = columns.TextColumn("Winner", sources=['get_rankings'],
                                    processor=itemgetter(0))

        # Take instance.description[:30] and append "..." to the end if truncation occurs.
        description = columns.TextColumn("Description", sources=['description'],
                                         processor=itemgetter(slice(None, 30), ellipsis=True))

    """

    def helper(instance, *args, **kwargs):
        default_value = kwargs.get("default_value")
        if default_value is None:
            default_value = instance
        value = default_value[k]
        if (
            ellipsis
            and isinstance(k, slice)
            and isinstance(value, str)
            and len(default_value) > len(value)
        ):
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
    Looks up ``attr`` on the target value. If the result is a callable, it will be called in place
    without arguments.

    If a ``key`` is given, it may be a function which maps the target value to something else
    before the attribute lookup takes place.

    Examples::

        # Explicitly selecting the sources and then using a processor to allow the model
        # method to organize the data itself, you can still provide all the necessary
        # ORM hints to the column.
        # This is definitely superior to having sources=['get_address'].
        address = columns.TextColumn("Address", sources=['street', 'city', 'state', 'zip'],
                                     processor=attrgetter('get_address'))

    """

    def helper(instance, *args, **kwargs):
        value = instance
        for bit in attr.split("."):
            value = getattr(value, bit)
            if callable(value):
                value = value()
        return value

    if key:
        helper = keyed_helper(helper)(key=key)
    return helper


def format_date(format_string, localize=False, key=None):
    """
    A pre-called helper to supply a date format string ahead of time, so that it can apply to each
    date or datetime that this column represents.  With Django >= 1.5, the ``localize=True`` keyword
    argument can be given, or else can be supplied in the column's own declaration for the same
    effect.  (The date and datetime columns explicitly forward their ``localize`` setting to all
    helpers.)

    If the ``key`` argument is given, it may be a function which maps the target value to something
    else before the date formatting takes place.
    """

    if localize is not False and localtime is None:
        raise Exception("Cannot use format_date argument 'localize' with Django < 1.5")

    def helper(value, *args, **kwargs):
        inner_localize = kwargs.get("localize", localize)
        if inner_localize is not False and localtime is None:
            raise Exception("Cannot use format_date argument 'localize' with Django < 1.5")

        if key:
            value = key(value)
        else:
            value = kwargs.get("default_value", value)
        if not value:  # Empty or missing default_value
            return ""
        if localize:
            value = localtime(value)
        return value.strftime(format_string)

    if key:
        return keyed_helper(helper)(key=key)
    return helper


def format(format_string, cast=lambda x: x):
    """
    A pre-called helper to supply a modern string format (the kind with {} instead of %s), so that
    it can apply to each value in the column as it is rendered.  This can be useful for string
    padding like leading zeroes, or rounding floating point numbers to a certain number of decimal
    places, etc.

    If given, the ``cast`` argument should be a mapping function that coerces the input to whatever
    type is required for the string formatting to work.  Trying to push string data into a float
    format will raise an exception, for example, so the ``float`` type itself could be given as
    the ``cast`` function.

    Examples::

        # Perform some 0 padding
        item_number = columns.FloatColumn("Item No.", sources=['number'],
                                          processor=format("{:03d}))

        # Force a string column value to coerce to float and round to 2 decimal places
        rating = columns.TextColumn("Rating", sources=['avg_rating'],
                                    processor=format("{:.2f}", cast=float))

    """

    def helper(instance, *args, **kwargs):
        value = kwargs.get("default_value")
        if value is None:
            value = instance
        value = cast(value)
        return format_string.format(value, obj=instance)

    return helper


def make_xeditable(instance=None, extra_attrs=[], *args, **kwargs):  # noqa: C901
    """
    Converts the contents of the column into an ``<a>`` tag with the required DOM attributes to
    power the X-Editable UI.

    The following keyword arguments are all optional, but may be provided when pre-calling the
    helper, to customize the output of the helper once it is run per object record:

        * ``type`` - Defaults to the basic type of the HTML input ("text", "number", "datetime")
        * ``title`` - Defaults to an empty string, controls the HTML "title" attribute.
        * ``placeholder`` - Defaults to whatever "title" is, controls the HTML
            "placeholder" attribute.
        * ``url`` - Defaults to the ``request.path`` of the view, which will automatically
            serve the X-Editable interface as long as it inherits from ``XEditableDatatableView``.
        * ``source`` - Defaults to the ``request.path`` of the view, which will automatically
            serve X-Editable requests for ``choices`` data about a field.

    Supplying a list of names via ``extra_attrs`` will enable arbitrary other keyword arguments to
    be rendered in the HTML as attribute as well.  ``extra_attrs`` serves as a whitelist of extra
    names so that unintended kwargs don't get rendered without your permission.
    """

    if instance is None:
        # Preloading kwargs into the helper for deferred execution
        helper = partial(make_xeditable, extra_attrs=extra_attrs, *args, **kwargs)
        return helper

    # Immediate finalization, return the xeditable structure
    data = kwargs.get("default_value", instance)
    rich_data = kwargs.get("rich_value", data)

    # Compile values to appear as "data-*" attributes on the anchor tag
    default_attr_names = ["pk", "type", "url", "source", "title", "placeholder"]
    valid_attr_names = set(default_attr_names + list(extra_attrs))
    attrs = {}
    for k, v in kwargs.items():
        if k in valid_attr_names:
            if k.startswith("data_"):
                k = k[5:]
            attrs["data-{0}".format(k)] = v

    attrs["data-xeditable"] = "xeditable"

    # Assign default values where they are not provided

    field_name = kwargs["field_name"]  # sent as a default kwarg to helpers
    if isinstance(field_name, (tuple, list)):
        # Legacy syntax
        field_name = field_name[1]
        if isinstance(field_name, (tuple, list)):
            raise ValueError(
                "'make_xeditable' helper needs a single-field data column,"
                " not {0!r}".format(field_name)
            )
    attrs["data-name"] = field_name

    if isinstance(rich_data, Model):
        attrs["data-value"] = rich_data.pk
    else:
        attrs["data-value"] = rich_data

    if "data-pk" not in attrs:
        attrs["data-pk"] = instance.pk

    if "data-url" not in attrs:
        # Look for a backup data-url
        provider_name = "get_update_url"
        url_provider = getattr(kwargs.get("view"), provider_name, None)
        if not url_provider:
            url_provider = getattr(instance, provider_name, None)
            if not url_provider and "view" in kwargs:
                url_provider = lambda field_name: kwargs["view"].request.path  # noqa: E731
            else:
                raise ValueError("'make_xeditable' cannot determine a value for 'url'.")
        if url_provider:
            attrs["data-url"] = url_provider(field_name=field_name)

    if "data-placeholder" not in attrs:
        attrs["data-placeholder"] = attrs.get("data-title", "")

    if "data-type" not in attrs:
        if hasattr(instance, "_meta"):
            # Try to fetch a reasonable type from the field's class
            if field_name == "pk":  # special field name not in Model._meta.fields
                field = instance._meta.pk
            else:
                field = resolve_orm_path(instance, field_name)

            if field.choices:
                field_type = "select"
            else:
                field_type = XEDITABLE_FIELD_TYPES.get(field.get_internal_type(), "text")
        else:
            field_type = "text"
        attrs["data-type"] = field_type

    # type=select elements need to fetch their valid choice options from an AJAX endpoint.
    # Register the view for this lookup.
    if attrs["data-type"] in ("select", "select2"):
        if "data-source" not in attrs:
            if "view" in kwargs:
                attrs["data-source"] = "{url}?{field_param}={fieldname}".format(
                    **{
                        "url": kwargs["view"].request.path,
                        "field_param": kwargs["view"].xeditable_fieldname_param,
                        "fieldname": field_name,
                    }
                )
                if attrs["data-type"] == "select2":
                    attrs["data-source"] += "&select2=true"
            else:
                raise ValueError("'make_xeditable' cannot determine a value for 'source'.")

        # Choice fields will want to display their readable label instead of db data
        data = getattr(instance, "get_{0}_display".format(field_name), lambda: data)()

    data = """<a href="#"{attrs}>{data}</a>""".format(attrs=flatatt(attrs), data=data)
    return data


def make_processor(func, arg=None):
    """
    A pre-called processor that wraps the execution of the target callable ``func``.

    This is useful for when ``func`` is a third party mapping function that can take your column's
    value and return an expected result, but doesn't understand all of the extra kwargs that get
    sent to processor callbacks.  Because this helper proxies access to ``func``, it can hold back
    the extra kwargs for a successful call.

    ``func`` will be called once per object record, a single positional argument being the column
    data retrieved via the column's :py:attr:`~datatableview.columns.Column.sources`

    An optional ``arg`` may be given, which will be forwarded as a second positional argument to
    ``func``.  This was originally intended to simplify using Django template filter functions as
    ``func``.  If you need to sent more arguments, consider wrapping your ``func`` in a
    ``functools.partial``, and use that as ``func`` instead.
    """

    def helper(instance, *args, **kwargs):
        value = kwargs.get("default_value")
        if value is None:
            value = instance
        if arg is not None:
            extra_arg = [arg]
        else:
            extra_arg = []
        return func(value, *extra_arg)

    return helper


through_filter = make_processor
