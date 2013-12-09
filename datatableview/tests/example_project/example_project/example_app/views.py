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
    implementation = """Missing implementation details!"""

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


class ColumnBackedByMethodDatatableView(DemoMixin, DatatableView):
    """
    Model methods can power columns instead of concrete fields.  This approach is similar to using
    a callback to supply a value for a virtual column, but demonstrates that non-field data sources
    may be used on the model without custom callbacks.

    In this situation, the ``pub_date`` is fetched using an example method ``get_pub_date()``. The
    column is technically sortable by default, but the operation takes place in code, rather than
    in the database.  Searching is not currently possible because of prohibitive performance
    penalties for large data sets.

    This strategy works nicely for fields that have a ``choices`` list, allowing you to use the
    ``get_FOO_display()`` method Django puts on the model instance.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'blog',
            'headline',
            ("Publication date", 'get_pub_date'),
        ],
    }

    implementation = """
    class ColumnBackedByMethodDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'blog',
                'headline',
                ("Publication date", 'get_pub_date'),  # get_pub_date is an attribute on the model
            ],
        }
    """


class CompoundColumnsDatatableView(DemoMixin, DatatableView):
    """
    Simple columns might only need one model field to represent their data, even when marked up by
    a callback function.  However, if a column actually represents more than one model field, the
    list of those fields can be given in place of a single field name.

    INFO:
    You'll probably want to use a callback in order to decide how these values should be sorted out.
    The default strategy if no callback is supplies is to join the values with ``" "``.  The utility
    of this might be limited, but it's a reasonable default to give you a starting point.

    Compound columns should target fields, not merely foreign keys.  For example, you might indeed
    want the ``unicode(entry.blog)`` representation to appear in the marked-up column data, but be
    sure to target the specific fields on ``Blog`` that are represented in that display.

    Specifying all of the relevent fields in a compound column helps make searching and sorting more
    natural.  Sorting a compound column is the same as giving the field list to a call to the
    queryset ``order_by()`` method.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'id',
            ("Headline", ['headline', 'blog__name'], 'get_headline_data'),
        ],
    }

    def get_headline_data(self, instance, *args, **kwargs):
        return "%s (%s)" % (instance.headline, instance.blog.name)

    implementation = u"""
        class CompoundColumnDatatableView(DatatableView):
            model = Entry
            datatable_options = {
                'columns': [
                    'id',
                    ("Headline", ['headline', 'blog__name'], 'get_headline_data'),
                ],
            }

            def get_headline_data(self, instance, *args, **kwargs):
                return "%s (%s)" % (instance.headline, instance.blog.name)

    """


class RelatedFieldsDatatableView(DemoMixin, DatatableView):
    """
    The standard ``"__"`` related field syntax is supported in the model field names for a column.
    The only limitation is that the field's pretty-name should be explicitly given.
    
    Sorting, searching, and value callbacks work on these columns as well.

    INFO:
    When a value callback is used on a column, it receives the row's ``instance``, and various
    keyword arguments to give the callback some context about the value.  Callbacks always receive
    an argument ``default_value``, which is the value as fetched from the target field.  You can
    leverage this to avoid recalculating the same value from attribute lookups in your callbacks.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'id',
            'headline',
            ("Blog name", 'blog__name'),
            ("Blog ID", 'blog__id'),
            'pub_date',
        ],
    }
    
    implementation = u"""
    class RelatedFieldsDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'id',
                'headline',
                ("Blog name", 'blog__name'),
                ("Blog ID", 'blog__id'),
                'pub_date',
            ],
        }
    """


class DefaultCallbackNamesDatatableView(DemoMixin, DatatableView):
    """
    If a column definition hasn't supplied an explicit callback value processor, there is a default
    method that will be looked up on the view instance in the format of ``get_column_FOO_data()``.

    If the field has defined a "pretty name" in the tuple format, the pretty name will be used for
    the basis of looking up this default callback.  This is to avoid the complexities of mangling an
    automatic name that makes sense for compound and virtual columns.
    
    "Pretty names" put through the mangling process essentially normalize non-letter non-number
    characters to underscores, and multiple adjacent underscores are collapsed to a single
    underscore.  It's like a slugify process, but using ``"_"`` and without lowercasing.

    If the name mangling is ever unintuitive or cumbersome to remember or guess, you can either
    supply your own callback names as the third item in a column's 3-tuple definition, or else
    define a callback using the 0-based index instead of the field name, such as
    ``get_column_0_data()``.

    INFO:
    The default hook is only executed if there is no callback already supplied in the column
    definition.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'id',
            'headline',
            'body_text',
            'blog',
            ("Publication Date", 'pub_date'),
        ],
    }

    def get_column_body_text_data(self, instance, *args, **kwargs):
        return instance.body_text[:30]

    def get_column_Publication_Date_data(self, instance, *args, **kwargs):
        return instance.pub_date.strftime("%m/%d/%Y")

    implementation = u"""
    class DefaultCallbackNamesDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'id',
                'headline',
                'body_text',
                'blog',
                ("Publication Date", 'pub_date'),
            ],
        }

        def get_column_body_text_data(self, instance, *args, **kwargs):
            return instance.body_text[:30]

        def get_column_Publication_Date_data(self, instance, *args, **kwargs):
            return instance.pub_date.strftime("%m/%d/%Y")
    """

class UnsortableColumnsDatatableView(DemoMixin, DatatableView):
    """
    Columns that should be blocked from sorting (on the frontend and also by the backend) can be
    enumerated in the ``datatable_options['unsortable_columns']`` key.

    When the table structure is initially rendered onto the page, the ``&lt;th&gt;`` elements are
    given attributes in a ``data-*`` API fashion.  (dataTables.js does not actually support this
    API, but it greatly simplifies the legwork required to get a table automatically initialized.)
    For sorting, the data attribute is ``data-sortable``, the value being ``"true"`` by default,
    but ``"false"`` if the column name is given in the unsortable columns list.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'id',
            'headline',
            'blog',
            'pub_date',
        ],
        'unsortable_columns': ['headline', 'blog', 'pub_date'],
    }

    implementation = u"""
    class UnsortableColumnsDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'id',
                'headline',
                'body_text',
                'blog',
                'pub_date',
            ],
            'unsortable_columns': ['headline', 'body_text', 'blog', 'pub_date'],
        }
    """
