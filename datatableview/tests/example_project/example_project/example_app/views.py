from os import sep
import os.path
import re

import django
from django.views.generic import View, TemplateView
from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.defaultfilters import timesince

import datatableview
from datatableview.views import DatatableView, XEditableDatatableView
from datatableview.utils import get_datatable_structure
from datatableview import helpers

from .models import Entry, Blog

class ResetView(View):
    """ Google App Engine view for reloading the database to a fresh state every 24 hours. """
    def get(self, request, *args, **kwargs):
        from django.core.management import call_command
        from django.http import HttpResponse
        call_command('syncdb')
        return HttpResponse("Done.")


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

        # Versions
        context.update({
            'datatableview_version': '.'.join(map(str, datatableview.__version_info__)),
            'django_version': django.get_version(),
        })

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
        name = re.sub(r'([a-z]|[A-Z]+)(?=[A-Z])', r'\1_', name)
        return ["demos/" + name.lower() + ".html", "example_base.html"]

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
    class PrettyNamesDatatableView(DatatableView):
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
    Columns that have values derived at runtime by callbacks located on the view should specify
    their field as ``None``, and then provide a callback name or function reference.

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


class ManyToManyFieldsDatatableView(DemoMixin, DatatableView):
    """
    ``ManyToManyField`` relationships should not be specified directly as a column's data source.
    There's too much missing information, and the field name or field list should enumerate the
    real data points that are being shown.

    The most straightforward way to reveal a plural set of objects is to create your own callback
    handler that handles each item in the relationship as you see fit.  For example, combined with
    the ``helpers`` module, you can quickly make links out of the objects in the relationship.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'id',
            'headline',
            ("Authors", 'authors__name', 'get_author_names'),
            ("Authors", 'authors__name', 'get_author_names_as_links'),
        ],
    }

    def get_author_names(self, instance, *args, **kwargs):
        return ", ".join([author.name for author in instance.authors.all()])

    def get_author_names_as_links(self, instance, *args, **kwargs):
        return ", ".join([helpers.link_to_model(author) for author in instance.authors.all()])

    implementation = u"""
    class ManyToManyFields(DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'id',
                'headline',
                ("Authors", 'authors__name', 'get_author_names'),
                ("Authors", 'authors__name', 'get_author_names_as_links'),
            ],
        }

        def get_author_names(self, instance, *args, **kwargs):
            return ", ".join([author.name for author in instance.authors.all()])

        def get_author_names_as_links(self, instance, *args, **kwargs):
            from datatableview import helpers
            return ", ".join([helpers.link_to_model(author) for author in instance.authors.all()])
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

class XEditableColumnsDatatableView(DemoMixin, XEditableDatatableView):
    """
    The <a href="http://vitalets.github.io/x-editable/">x-editable</a> javascript tool is a way to
    turn table cells into interactive forms that can post incremental updates over ajax.  x-editable
    supports Bootstrap, jQueryUI, and plain jQuery.  It requires its own specific initialization to
    take place after the datatable has populated itself with data.

    To enable x-editable columns, inherit your view from ``XEditableDatatableView`` instead of the
    plain ``DatatableView``.  The x-editable variant has ajax responders built into it so that the
    incremental updates can be received, validated, and responded to.  Choices lists are also
    fetched over ajax by the x-editable Javascript library, so this specialized view also responds
    to those.

    Next, use the ``datatableview.helpers.make_xeditable`` function as a callback for the columns
    that should become interactive.  You can customize the helper's behavior, but by default,
    ``make_xeditable`` will try to pick reasonable defaults for the field type.  This callback
    returns a ``&lt;a&gt;`` tag with ``data-*`` API attributes on it that the x-editable javascript
    knows how to read.

    Finally, on your template you will need to include a special initialization to make sure that
    the frontend understands how to handle what you've set up.  The global Javascript object
    ``datatableview`` has a member called ``make_xeditable`` (named after the helper function you
    use in the column definitions), which is a factory that returns a callback for the dataTables.js
    ``fnRowCallback`` hook.  See the implementation snippets below.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'id',
            ("Headline", 'headline', helpers.make_xeditable),
            ("Blog", 'blog', helpers.make_xeditable),
            ("Published date", 'pub_date', helpers.make_xeditable),
        ]
    }

    implementation = u"""
    class XEditableColumnsDatatableView(XEditableDatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'id',
                ("Headline", 'headline', helpers.make_xeditable),
                ("Blog", 'blog', helpers.make_xeditable),
                ("Published date", 'pub_date', helpers.make_xeditable),
            ]
        }
    </pre>
    <pre class="brush: javascript">
    // Page javascript
    datatableview.auto_initialize = false;
    $(function(){
        var xeditable_options = {};
        datatableview.initialize($('.datatable'), {
            fnRowCallback: datatableview.make_xeditable(xeditable_options),
        });
    })
    """


class HelpersReferenceDatatableView(DemoMixin, XEditableDatatableView):
    """
    ``datatableview.helpers`` is a module decidated to functions that can be supplied directly as
    column callback functions.  Some of them are easy to use at runtime in your own callbacks,
    making some work easier for you, but the majority aim to solve common problems with as little
    fuss as possible.
    """
    model = Entry
    datatable_options = {
        'columns': [
            ("ID", 'id', helpers.link_to_model),
            ("Blog", 'blog__name', helpers.link_to_model(key=lambda instance: instance.blog)),
            ("Headline", 'headline', helpers.make_xeditable),
            ("Body Text", 'body_text', helpers.itemgetter(slice(0, 30))),
            ("Publication Date", 'pub_date', helpers.format_date('%A, %b %d, %Y')),
            ("Modified Date", 'mod_date'),
            ("Age", 'pub_date', helpers.through_filter(timesince)),
            ("Interaction", 'get_interaction_total', helpers.make_boolean_checkmark),
            ("Comments", 'n_comments', helpers.format("{0:,}")),
            ("Pingbacks", 'n_pingbacks', helpers.format("{0:,}")),
        ],
    }

    implementation = u"""
    class HelpersReferenceDatatableView(XEditableDatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                ("ID", 'id', helpers.link_to_model),
                ("Blog", 'blog__name', helpers.link_to_model(key=lambda instance: instance.blog)),
                ("Headline", 'headline', helpers.make_xeditable),
                ("Body Text", 'body_text', helpers.itemgetter(slice(0, 30))),
                ("Publication Date", 'pub_date', helpers.format_date('%A, %b %d, %Y')),
                ("Modified Date", 'mod_date'),
                ("Age", 'pub_date', helpers.through_filter(timesince)),
                ("Interaction", 'get_interaction_total', helpers.make_boolean_checkmark),
                ("Comments", 'n_comments', helpers.format("{0:,}")),
                ("Pingbacks", 'n_pingbacks', helpers.format("{0:,}")),
            ],
        }
    """


class OrderingDatatableView(DemoMixin, DatatableView):
    """
    Default ordering is normally controlled by the model's Meta option ``ordering``, which is a list
    of field names (possibly with a prefix ``"-"`` character to denote reverse order).
    
    ``datatable_options["ordering"]`` is the same kind of list, with the exception that it should
    target virtual and compound fields by their "pretty name", which is the first item in the column
    definition tuple.
    """
    model = Entry
    datatable_options = {
        'columns': [
            ("Pretty name", 'id'),
            'headline',
        ],
        'ordering': ['-id'],
    }

    implementation = u"""
    class OrderingDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'id',
                'headline',
            ],
            'ordering': ['-id'],
        }
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


class HiddenColumnsDatatableView(DemoMixin, DatatableView):
    """
    Columns may be marked for being hidden.  This is a client-side tweak that has no benefit to
    server performance.  When dataTables.js sees a column marked for being hidden, it removes it
    from the DOM, but retains traces of it in memory.  Some of the dataTables.js plugins have used
    this to allow you to send columns that are invisible on the main website, but if exported to
    CSV by the client, are included and visible as usual.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'id',
            'headline',
            'blog',
            'pub_date',
        ],
        'hidden_columns': ['id'],
    }

    implementation = u"""
    class HiddenColumnsDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'id',
                'headline',
                'blog',
                'pub_date',
            ],
            'hidden_columns': ['id'],
        }
    """


class SearchFieldsDatatableView(DemoMixin, DatatableView):
    """
    When a user searches a datatable, the server will query all of the concrete fields in the
    displayed columns.  You can enable extra search fields that are not shown on the table, but are
    consulted during a search query, by adding ``datatable_options["search_fields"]``.
    
    ``search_fields`` is a simple list of fields using the normal query language.  In this case,
    ``"blog__name"`` has been added to the list of fields, and so you can search the above table
    for the term ``First`` or ``Second`` and see the table filter the results, even though that
    field is not included as a real column.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'id',
            'headline',
            'pub_date',
        ],
        'search_fields': ['blog__name'],
    }

    implementation = u"""
    class SearchFieldsDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'id',
                'headline',
                'pub_date',
            ],
            'search_fields': ['blog__name'],
        }
    """


class CustomizedTemplateDatatableView(DemoMixin, DatatableView):
    """
    When the ``datatable`` context variable is rendered, it looks for a template named
    ``"datatableview/default_structure.html"``.  This template is pretty generic, but lacks special
    styles for UI frameworks like Twitter Bootstrap and others.

    The default template renders special ``data-*`` attributes on the ``table`` and ``th`` tags,
    which helps make initializing the tables more seamless when using the ``datatableview.js`` tool.

    Alternately, you can specify a custom template on a per-view basis using
    ``datatable_options["structure_template"]``, which is a normal template path that will be put
    through the Django discovery process.

    WARNING:
    When overriding this template, take care to render the ``data-*`` attributes if you want easy
    table initialization!
    """
    model = Entry
    datatable_options = {
        'structure_template': "custom_table_template.html",
        'columns': [
            'id',
            'headline',
            'blog',
            'pub_date',
        ],
    }

    implementation = u"""
    class CustomizedTemplateDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'structure_template': "custom_table_template.html",
            'columns': [
                'id',
                'headline',
                'blog',
                'pub_date',
            ],
        }
    """

class BootstrapTemplateDatatableView(DemoMixin, DatatableView):
    """
    The easiest way to get Bootstrap datatables is to use the alternate structural template
    ``datatableview/bootstrap_structure.html``, which simply adds the
    ``table``, ``table-striped``, and ``table-bordered`` classes to the main table tag.  You can
    specify the template directly in ``datatable_options["structure_template"]``, or you can create
    your own ``datatableview/default_structure.html`` template and simply paste the contents of the
    bootstrap version into it.
    
    WARNING:
    Overriding ``datatableview/default_structure.html`` will affect all datatables using the default
    template!

    This gets the table itself looking better, but the rest of the controls added by dataTables.js
    are a little lackluster by comparison.  To fix this, download the integration files from
    <a href="https://github.com/DataTables/Plugins/tree/master/integration/bootstrap/">https://github.com/DataTables/Plugins/tree/master/integration/bootstrap/</a>
    and then add them to the main template:
    
    <pre>
    &lt;link href="{{ STATIC_URL }}css/dataTables.bootstrap.css" rel="stylesheet" /&gt;
    </pre>
    <pre>
    &lt;script src="{{ STATIC_URL }}js/dataTables.bootstrap.js"&gt;&lt;/script&gt;
    </pre>

    Alternately, you can use the set of static resources from
    <a href="https://github.com/Jowin/Datatables-Bootstrap3/">https://github.com/Jowin/Datatables-Bootstrap3/</a>,
    which do the same thing with mild variances.
    """
    model = Entry
    datatable_options = {
        'structure_template': "datatableview/bootstrap_structure.html",
        'columns': [
            'id',
            'headline',
            'blog',
            'pub_date',
        ],
    }

    implementation = u"""
    class BootstrapTemplateOfficialDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'structure_template': "datatableview/bootstrap_structure.html",
            'columns': [
                'id',
                'headline',
                'blog',
                'pub_date',
            ],
        }
    """


class CSSStylingDatatableView(DemoMixin, DatatableView):
    """
    The default template used by the datatable context variable when you render it will include
    ``data-name`` attributes on the ``&lt;th&gt;`` column headers, which is the ``slugify``'d
    version of the column's label.  This makes sizing the columns very easy.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'id',
            'headline',
            'blog',
            ("Publication date", 'pub_date'),
        ],
    }

    implementation = u"""
    class CSSStylingDatatableView(DatatableView):
        model = Entry
        datatable_options = {
            'columns': [
                'id',
                'headline',
                'blog',
                'pub_date',
            ],
        }
    """


class MultipleTablesDatatableView(DemoMixin, DatatableView):
    """
    ``DatatableView`` makes the initial assumption that it will power just one queryset.  You can
    implement ``get_queryset()``, ``get_datatable_options()``, and ``get_datatable()`` methods that
    use switching behavior depending on which table is asking for updates. (More on how to flag
    that fact farther down.)

    WARNING:
    If more than one model class type might end up getting returned via the ``get_queryset()``
    method, as is the case in the following scenario, you should avoid setting the class attribute
    ``model``.  Instead, you can let the standard ``ListView`` mechanics that ``DatatableView`` uses
    automatically read the model class from the returned queryset from ``get_queryset()``.

    See the following examples for how to handle certain scenarios.
    
    The principle of the process is that you can override ``get_datatable_options()`` and
    ``get_datatable()`` to modify the structural objects that get returned by the view based on
    certain URL kwargs, GET data, etc.  If you examine the implementation code at the bottom of the
    page, you will see how these two methods have been customized to accept a ``type`` argument.
    This is used when the context data is originally fetched, so that we can request each table
    structure object.

    Once AJAX calls start happening on the page, each table structure needs to identify itself so
    that the view can deal with each one separately.  To accomplish this, our ``get_datatable()``
    implementation adds a GET parameter in the AJAX url for each table to distinguish them.  This
    parameter is fed back to us during AJAX calls.

    Finally, we can modify the ``get_queryset()`` method on the same principle; depending on the GET
    flag we've set up, the method should perhaps return customized content.

    Demo #1 in this series of examples is the default code path, where no modifications of any kind
    are at play.  Demo #2 slices off the ``"Header"`` column from the options of #1.  Demo #3 uses
    its own separate model and options.  All are identified separately in their AJAX queries by the
    variable we planted in each table's structure in ``get_context_data()``.
    """

    # Demo #1 and Demo # 2 will use variations of the same options.
    # Note that we're not setting the model here as usually.  See the warning above.
    datatable_options = {
        'columns': [
            'id',
            'headline',
        ],
    }

    # Demo #3 will use completely separate options.
    blog_datatable_options = {
        'columns': [
            'id',
            'name',
            'tagline',
        ],
    }

    def get_queryset(self, type=None):
        """
        Customized implementation of the queryset getter.  The custom argument ``type`` is managed
        by us, and is used in the context and GET parameters to control which table we return.
        """

        if type is None:
            type = self.request.GET.get('datatable-type', None)

        if type == "demo3":
            return Blog.objects.all()
        return Entry.objects.all()

    def get_datatable_options(self, type=None):
        """
        Customized implementation of the options getter.  The custom argument ``type`` is managed
        by us, and is used in the context and GET parameters to control which table we return.
        """

        if type is None:
            type = self.request.GET.get('datatable-type', None)

        options = self.datatable_options

        if type == "demo2":
            # If modifying the options, be sure make copies of the pieces you are changing, or else
            # you'll end up changing class-level definitions that are not thread-safe!
            options = self.datatable_options.copy()
            options['columns'] = options['columns'][1:]
        elif type == "demo3":
            # Return separate options settings
            options = self.blog_datatable_options

        return options

    def get_datatable(self, type=None):
        """
        Customized implementation of the structure getter.  The custom argument ``type`` is managed
        by us, and is used in the context and GET parameters to control which table we return.
        """
        if type is None:
            type = self.request.GET.get('datatable-type', None)

        if type is not None:
            datatable_options = self.get_datatable_options(type=type)
            # Put a marker variable in the AJAX GET request so that the table identity is known
            ajax_url = self.request.path + "?datatable-type={type}".format(type=type)

        if type == "demo2":
            datatable = get_datatable_structure(ajax_url, datatable_options, model=Entry)
        elif type == "demo3":
            # Change the reference model to Blog, instead of Entry
            datatable = get_datatable_structure(ajax_url, datatable_options, model=Blog)
        else:
            return super(MultipleTablesDatatableView, self).get_datatable()

        return datatable
        

    def get_context_data(self, **kwargs):
        context = super(MultipleTablesDatatableView, self).get_context_data(**kwargs)
    
        # Get the other structure objects for the initial context
        context['modified_columns_datatable'] = self.get_datatable(type="demo2")
        context['blog_datatable'] = self.get_datatable(type="demo3")
        return context

    implementation = u'''
    from .models import Entry, Blog
    class MultipleTablesDatatableView(DatatableView):
        # Demo #1 and Demo # 2 will use variations of the same options
        model = Entry
        datatable_options = {
            'columns': [
                'id',
                'headline',
            ],
        }

        # Demo #3 will use completely separate options
        blog_datatable_options = {
            'columns': [
                'id',
                'name',
                'tagline',
            ],
        }

        def get_queryset(self, type=None):
            """
            Customized implementation of the queryset getter.  The custom argument ``type`` is managed
            by us, and is used in the context and GET parameters to control which table we return.
            """

            if type is None:
                type = self.request.GET.get('datatable-type', None)

            if type == "demo3":
                return Blog.objects.all()
            return super(MultipleTablesDatatableView, self).get_queryset()

        def get_datatable_options(self, type=None):
            """
            Customized implementation of the options getter.  The custom argument ``type`` is managed
            by us, and is used in the context and GET parameters to control which table we return.
            """

            if type is None:
                type = self.request.GET.get('datatable-type', None)

            options = self.datatable_options

            if type == "demo2":
                # If modifying the options, be sure make copies of the pieces you are changing, or else
                # you'll end up changing class-level definitions that are not thread-safe!
                options = self.datatable_options.copy()
                options['columns'] = options['columns'][1:]
            elif type == "demo3":
                # Return separate options settings
                options = self.blog_datatable_options

            return options

        def get_datatable(self, type=None):
            """
            Customized implementation of the structure getter.  The custom argument ``type`` is managed
            by us, and is used in the context and GET parameters to control which table we return.
            """
            if type is None:
                type = self.request.GET.get('datatable-type', None)

            if type is not None:
                datatable_options = self.get_datatable_options(type=type)
                # Put a marker variable in the AJAX GET request so that the table identity is known
                ajax_url = self.request.path + "?datatable-type={type}".format(type=type)

            if type == "demo2":
                datatable = get_datatable_structure(ajax_url, datatable_options, model=Blog)
            elif type == "demo3":
                # Change the reference model to Blog, instead of Entry
                datatable = get_datatable_structure(ajax_url, datatable_options, model=Entry)
            else:
                return super(MultipleTablesDatatableView, self).get_datatable()

            return datatable
        

        def get_context_data(self, **kwargs):
            context = super(MultipleTablesDatatableView, self).get_context_data(**kwargs)

            # Get the other structure objects for the initial context
            context['modified_columns_datatable'] = self.get_datatable(type="demo2")
            context['blog_datatable'] = self.get_datatable(type="demo3")
            return context
    '''


class EmbeddedTableDatatableView(DemoMixin, TemplateView):
    """
    To embed a datatable onto a page that shouldn't be responsible for generating all of the ajax
    queries, you can easily just create the structure object that serves as the context variable,
    but base it on the options of some other view.  The other view will indeed need access to those
    options once queries begin to autonomously route to it over AJAX, so you won't be able to
    specify the column options directly inside of the ``get_context_data()``, but you can get pretty
    close.

    In this example, we've created a separate view, called ``SatelliteDatatableView``, which houses
    all of the options and machinery for getting the structure object for the context.

    Just add a ``get_context_data()`` method, instantiate the other view, and ask it to generate
    the options object via ``get_datatable_options()``.  You can feed this options object into 
    the ``datatableview.utils.get_datatable_structure()`` utility.
    
    ``get_datatable_structure()`` takes at least two arguments, and is the mechanism that a regular
    call to a ``DatatableView.get_datatable()`` uses to get the context variable: the ``ajax_url``
    the table will target, and the ``options`` object.  Unless there are ordering options set in
    the main ``datatable_options`` object, the table won't know how to use default ordering, so you
    can specify the third optional argument ``model``.
    """

    def get_context_data(self, **kwargs):
        context = super(EmbeddedTableDatatableView, self).get_context_data(**kwargs)

        satellite_view = SatelliteDatatableView()
        options = satellite_view.get_datatable_options()
        datatable = get_datatable_structure(reverse('satellite'), options)

        context['datatable'] = datatable
        return context

    implementation = u'''
    class EmbeddedTableDatatableView(TemplateView):
        def get_context_data(self, **kwargs):
            context = super(EmbeddedTableDatatableView, self).get_context_data(**kwargs)

            satellite_view = SatelliteDatatableView()
            options = satellite_view.get_datatable_options()
            datatable = get_datatable_structure(reverse('satellite'), options)

            context['datatable'] = datatable
            return context

    class SatelliteDatatableView(DatatableView):
        """
        External view powering the embedded table for ``EmbeddedTableDatatableView``.
        """
        model = Entry
        datatable_options = {
            'columns': [
                'id',
                'headline',
                'pub_date',
            ],
        }
    '''

class SatelliteDatatableView(DatatableView):
    """
    External view powering the embedded table for ``EmbeddedTableDatatableView``.
    """
    template_name = "blank.html"
    model = Entry
    datatable_options = {
        'columns': [
            'id',
            'headline',
            'pub_date',
        ],
    }
