"""
A collection of small helper functions for generating small pieces of datatable output in custom
methods on a view.

Because of uncontrolled external use of ``preload_record_data()`` by the view, each of these utility
functions allows for generic ``*args`` to pass through to the function, even though they aren't used
in any way.

"""

def link_to_model(instance, text=None, *args, **kwargs):
    return """<a href="{}">{}</a>""".format(instance.get_absolute_url(), text or unicode(instance))

def make_boolean_checkmark(value, false_value=""):
    if value:
        return "&#10004;"
    return false_value