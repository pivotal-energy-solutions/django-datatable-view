from os import sep
import os.path
import re

from django.views.generic import TemplateView
from django.conf import settings
from django.template.defaultfilters import timesince

from datatableview.views import DatatableView, XEditableDatatableView

from .models import Entry

class IndexView(TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)

        # Try to determine if the user jumped the gun on testing things out
        db_works = True
        try:
            list(Entry.objects.all()[:1])
        except:
            db_works = False
        context['db_works'] = db_works

        path, working_directory = os.path.split(os.path.abspath('.'))
        context['working_directory'] = working_directory
        context['os_sep'] = sep

        return context


class JavascriptInitializationView(TemplateView):
    template_name = "javascript_initialization.html"


class ValidColumnFormatsView(TemplateView):
    template_name = "valid_column_formats.html"


class DemoMixin(object):
    description = """Missing description!"""
    implementation = """<pre>Missing implementation details!</pre>"""

    def get_template_names(self):
        """ Try the view's snake_case name, or else use default simple template. """
        name = self.__class__.__name__.replace("DatatableView", "")
        folder = "datatable"
        if name.endswith("XEditable"):
            folder = "xeditable"
            name = name.replace("XEditable", "")
        name = re.sub(r'([a-z]|[A-Z]+)(?=[A-Z])', r'\1_', name)
        return [os.path.join(folder, name.lower() + ".html"), "example_base.html"]

    def get_context_data(self, **kwargs):
        context = super(DemoMixin, self).get_context_data(**kwargs)
        context['implementation'] = self.implementation

        # Unwrap the lines of description text so that they don't linebreak funny after being put
        # through the ``linebreaks`` template filter.
        alert_types = ['info', 'warning', 'danger']
        paragraphs = []
        p = []
        alert = False
        for line in self.__doc__.splitlines():
            line = line[4:].rstrip()
            if not line:
                if alert:
                    p.append(u"""</div>""")
                    alert = False
                paragraphs.append(p)
                p = []
            elif line.lower()[:-1] in alert_types:
                p.append(u"""<div class="alert alert-{type}">""".format(type=line.lower()[:-1]))
                alert = True
            else:
                p.append(line)
        description = "\n\n".join(" ".join(p) for p in paragraphs)
        context['description'] = re.sub(r'``(.*?)``', r'<code>\1</code>', description)

        return context

class ZeroConfigurationDatatableView(DemoMixin, DatatableView):
    """
    If no columns are specified in the view's ``datatable_options`` attribute, ``DatatableView``
    will use all of the model's local fields. Note that this does not include reverse
    relationships, many-to-many fields (even if the ``ManyToManyField`` is defined on the model
    directly), or the special ``pk`` field.

    Note that fields will attempt to use their ``verbose_name``, if available.

    WARNING:
    Having ``ForeignKey`` as a visible column will generate extra queries per displayed row, due to
    the way attribute lookup will cause Django to go fetch the related object. Implement a
    ``get_queryset()`` method on your view that returns a queryset with the appropriate call to
    ``select_related()``.
    """

    model = Entry
    datatable_options = {}

    implementation = u"""
    class ZeroConfigurationDatatableView(DatatableView):
        model = Entry
    """

class SpecificColumnsDatatableView(DemoMixin, DatatableView):
    """
    To target specific columns that should appear on the table, use the
    ``datatable_options['columns']`` key in the configuration.  Specify a tuple or list of model
    field names, in the order that they are to appear on the table.
    
    Note that fields will attempt to use their ``verbose_name``, if available.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'id',
            'headline',
            'blog',
            'pub_date',
        ]
    }

    implementation = u"""
    class SpecificColumnsDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'id',
                'headline',
                'blog',
                'pub_date',
            ]
        }
    """

class PrettyNamesDatatableView(DemoMixin, DatatableView):
    """
    By converting a column's definition to a 2-tuple, you can specify a verbose name that should
    appear as the column header.  In this example, the ``pub_date`` field has been given a special
    verbose name ``"Publication date"``.
    
    This becomes particularly useful when the field is virtualized (i.e., not tied to a specific
    model field).
    """
    model = Entry
    datatable_options = {
        'columns': [
            'blog',
            'headline',
            ("Publication date", 'pub_date'),
            'n_comments',
            'rating',
        ]
    }

    implementation = u"""
    class PrettyNamesDatatableView(DemoMixin, DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'blog',
                'headline',
                ("Publication date", 'pub_date'),
                'n_comments',
                'rating',
            ]
        }
    """


class PresentationalChangesDatatableView(DemoMixin, DatatableView):
    """
    This table actually uses the same column twice; the first time is for a raw display of the
    ``pub_date`` value, and the second is for a humanized version of the same information via the
    template filter ``timesince``.
    
    Note that the ``Age`` column is sortable using the underlying data from the ``pub_date`` field,
    and is not actually sorting the presentionally modified text of the frontend.

    Callbacks should take the ``instance`` represented by the row, and ``*args`` and ``**kwargs``
    to maximize flexibility with future data arguments sent by the callback dispatcher.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'blog',
            'headline',
            ("Publication date", 'pub_date'),
            ("Age", 'pub_date', 'get_entry_age'),
        ],
    }

    def get_entry_age(self, instance, *args, **kwargs):
        return timesince(instance.pub_date)

    implementation = u"""
    from django.template.defaultfilters import timesince
    class PresentationalChangesDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'blog',
                'headline',
                ("Publication date", 'pub_date'),
                ("Age", 'pub_date', 'get_entry_age'),
            ],
        }

        def get_entry_age(self, instance, *args, **kwargs):
            return timesince(instance.pub_date)
    """


class VirtualColumnDefinitionsDatatableView(DemoMixin, DatatableView):
    """
    Columns that have values derived at runtime, either by callbacks located on the view or by
    readonly methods/attributes/properties on the model, should specify their field as ``None``,
    and then provide a callback name or function reference.

    Callbacks should take the ``instance`` represented by the row, and ``*args`` and ``**kwargs``
    to maximize flexibility with future data arguments sent by the callback dispatcher.

    Callbacks can be used for concrete fields too.

    INFO:
    The ``Age`` column could actually still specify its model field as ``pub_date``, but it was
    omitted specifically to demonstrate the bridging of the gap by the callback.  In this situation,
    the column is not searchable or sortable at the database level.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'blog',
            'headline',
            ("Age", None, 'get_entry_age'),
        ],
    }

    def get_entry_age(self, instance, *args, **kwargs):
        return timesince(instance.pub_date)

    implementation = u"""
    from django.template.defaultfilters import timesince
    class VirtualColumnDefinitionsDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'blog',
                'headline',
                ("Age", None, 'get_entry_age'),
            ],
        }

        def get_entry_age(self, instance, *args, **kwargs):
            return timesince(instance.pub_date)
    """
