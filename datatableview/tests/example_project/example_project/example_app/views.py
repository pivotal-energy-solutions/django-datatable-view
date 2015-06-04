# -*- encoding: utf-8 -*-

from os import sep
import os.path
import re

from django import get_version
from django.views.generic import View, TemplateView
from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.defaultfilters import timesince

import datatableview
from datatableview import Datatable, ValuesDatatable, columns, SkipRecord
from datatableview.views import DatatableView, MultipleDatatableView, XEditableDatatableView
from datatableview.views.legacy import LegacyDatatableView, LegacyConfigurationDatatableView
from datatableview import helpers

from .models import Entry, Blog


if get_version().split('.') < ['1', '7']:
    initial_data_fixture = 'initial_data_legacy.json'
else:
    initial_data_fixture = 'initial_data_modern.json'


class ResetView(View):
    """ Google App Engine view for reloading the database to a fresh state every 24 hours. """
    def get(self, request, *args, **kwargs):
        from django.core.management import call_command
        from django.http import HttpResponse
        call_command('syncdb')
        call_command('loaddata', initial_data_fixture)
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
            'django_version': get_version(),
            'datatables_version': '1.10.0',
        })

        return context


class MigrationGuideView(TemplateView):
    template_name = "migration_guide.html"


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


# Configuration strategies
class ConfigureDatatableObject(DemoMixin, DatatableView):
    """
    Like the built-in Django forms framework, configuration can be wrapped up into a subclass of
    ``Datatable``, using class attributes to configure the columns (fields), while an inner ``Meta``
    class manages the options that aren't the column declarations themselves.
    """
    model = Entry
    class datatable_class(Datatable):
        class Meta:
            model = Entry
            columns = ['id', 'headline', 'pub_date', 'n_comments', 'n_pingbacks']
            ordering = ['-id']
            page_length = 5
            search_fields = ['blog__name']
            unsortable_columns = ['n_comments']
            hidden_columns = ['n_pingbacks']
            structure_template = 'datatableview/default_structure.html'

    implementation = u"""
    class MyDatatable(Datatable):
        class Meta:
            model = Entry
            columns = ['id', 'headline', 'pub_date', 'n_comments', 'n_pingbacks']
            ordering = ['-id']
            page_length = 5
            search_fields = ['blog__name']
            unsortable_columns = ['n_comments']
            hidden_columns = ['n_pingbacks']
            structure_template = 'datatableview/default_structure.html'

    class ConfigureDatatableObjectDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
    """

class ConfigureValuesDatatableObject(DemoMixin, DatatableView):
    """
    ``ValuesDatatable`` is a variant of the standard ``Datatable`` configuration object that
    leverages the very same interaction model.

    This version of the datatable object gets to make three very helpful assumptions about the data
    being displayed:

    <ol>
    <li>You want faster, smaller queries.</li>
    <li>``object_list`` is a QuerySet, not just a ``list``.</li>
    <li>The column definitions are capable of displaying data without the help of any of the model's
        methods.</li>
    </ol>

    If these things are true, you can use ``ValuesDatatable`` to have it flip the ``QuerySet`` into
    a ``ValuesQuerySet`` and fetch only the data that is referenced by your column definitions'
    ``sources`` declarations.

    INFO:
    The items in a ``ValuesQuerySet`` are not instances of your model, but are instead simple
    dictionaries, so you must avoid dotted attribute lookups.

    To reduce confusion about what names are being used to store values found by the ValuesQuerySet,
    (particularly in the case of related lookups such as ``blog__id``), some postprocessing is
    performed in the ``preload_record_data()`` hook.  A entry is made in the object dictionary for
    each column, where value is intuitively what you asked for.  If there was more than one ORM path
    named in the column's ``sources`` list, then you will find a corresponding list in your object
    with each of the values.

    To visualize what's being done here, here is a sample object that would be sent to column
    processor callbacks, which has keys for all ORM source names mixed with actual column names
    given by the configuration:
    """
    model = Entry
    class datatable_class(ValuesDatatable):
        blog = columns.TextColumn("Blog", sources=['blog__id', 'blog__name'])
        publication_date = columns.DateColumn("Publication Date", sources=['pub_date'])

        class Meta:
            model = Entry
            columns = ['id', 'blog', 'headline', 'publication_date', 'n_comments', 'n_pingbacks']

    implementation = u"""
    class MyDatatable(ValuesDatatable):
        blog = columns.TextColumn("Blog", sources=['blog__id', 'blog__name'])
        publication_date = columns.DateColumn("Publication Date", sources=['pub_date'])

        class Meta:
            model = Entry
            columns = ['id', 'blog', 'headline', 'publication_date', 'n_comments', 'n_pingbacks']

    class ConfigureValuesDatatableObjectDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
    """


class ConfigureInline(DemoMixin, DatatableView):
    """
    Someone making a view that requires little configuration might reasonably find it midly
    cumbersome to declare a full ``Datatable`` class just to specify a single setting.  In the style
    of the built-in Django generic class-based views, ``DatatableView`` will inspect its own
    attributes before automatically constructing a plain Datatable object to power the view.

    All of the available settings can be given in this format, and can even be combined with the use
    of the ``datatable_class`` setting.  Attributes on the view will override the settings from a
    Datatable instance during instantiation, which makes simple tweaks to generic Datatable objects
    very easy.
    """
    model = Entry
    columns = ['id', 'headline', 'pub_date']

    implementation = u"""
    class ConfigureInlineDatatableView(DatatableView):
        model = Entry
        columns = ['id', 'headline', 'pub_date']


    # Specifying a datatable_class does not harm the configuration, but combines them
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline', 'pub_date']
    class ConfigureCombinedDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
        columns = ['headline', 'pub_date']
    """


class ConfigureDatatableOptions(DemoMixin, LegacyDatatableView):
    """
    WARNING:
    Avoid using this configuration strategy, as it will be removed in the 1.0 release.

    Before version 0.9, the configuration strategy resembled that of the inline style using the
    view's class attributes, except that all of the available settings were put inside of one
    dictionary called ``datatable_options``.

    This strategy is still made available for migration purposes by importing and subclassing your
    view from one of ``LegacyConfigurationDatatableView`` or ``LegacyDatatableView`` from
    ``datatableview.views.legacy``.

    INFO:
    Use ``LegacyConfigurationDatatableView`` if all you want is to allow your ``datatable_options``
    dict to be discovered, but use ``LegacyDatatableView`` if you were hacking the old view up and
    crying like it was onions.

    ``LegacyDatatableView`` not only uses the legacy configuration style but also preserves the
    method structure of the old DatatableView. A few private imports were moved from
    ``datatableview.utils`` into ``datatableview.views.legacy``, but aside from that, method
    overrides on the old view should work the same on this one.
    """
    model = Entry
    datatable_options = {
        'columns': [
            'id',
            ("Publication Date", 'pub_date'),
            'headline',
        ],
    }

    implementation = u"""
    # If all you need is old-style configuration:
    from datatableview.views.legacy import LegacyConfigurationDatatableView
    class LegacyConfigDatatableView(LegacyConfigurationDatatableView):
        model = Entry
        datatable_options = {
            'columns': ['id', ("Publication Date", 'pub_date'), 'headline'],
        }

    # If you need an ambulance:
    from datatableview.views.legacy import LegacyDatatableView
    class LegacyEverythingDatatableView(LegacyDatatableView):
        model = Entry
        datatable_options = {
            'columns': ['id', ("Publication Date", 'pub_date'), 'headline'],
        }
    """


# Column configurations
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
    class datatable_class(Datatable):
        class Meta:
            columns = ['id', 'headline', 'blog', 'pub_date']

    implementation = u"""
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline', 'blog', 'pub_date']

    class SpecificColumnsDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
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
    class datatable_class(Datatable):
        class Meta:
            columns = ['blog', 'headline', 'pub_date', 'n_comments', 'rating']
            labels = {
                'pub_date': "Publication date",
            }

    implementation = u"""
    class MyDatatable(Datatable):
        class Meta:
            columns = ['blog', 'headline', 'pub_date', 'n_comments', 'rating']
            labels = {
                'pub_date': "Publication date",
            }

    class PrettyNamesDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
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
    class datatable_class(Datatable):
        age = columns.TextColumn("Age", sources=['pub_date'], processor='get_entry_age')

        class Meta:
            columns = ['blog', 'headline', 'pub_date', 'age']
            labels = {
                'pub_date': "Publication date",
            }

        def get_entry_age(self, instance, **kwargs):
            return timesince(instance.pub_date)

    implementation = u"""
    from django.template.defaultfilters import timesince

    class MyDatatable(Datatable):
        age = columns.TextColumn("Age", sources=['pub_date'], processor='get_entry_age')

        class Meta:
            columns = ['blog', 'headline', 'pub_date', 'age']
            labels = {
                'pub_date': "Publication date",
            }

        def get_entry_age(self, instance, **kwargs):
            return timesince(instance.pub_date)

    class PresentationalChangesDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
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
    class datatable_class(Datatable):
        age = columns.TextColumn("Age", sources=None, processor='get_entry_age')

        class Meta:
            columns = ['blog', 'headline', 'age']

        def get_entry_age(self, instance, **kwargs):
            return timesince(instance.pub_date)

    implementation = u"""
    from django.template.defaultfilters import timesince

    class MyDatatable(Datatable):
        age = columns.TextColumn("Age", sources=None, processor='get_entry_age')

        class Meta:
            columns = ['blog', 'headline', 'age']

        def get_entry_age(self, instance, **kwargs):
            return timesince(instance.pub_date)

    class VirtualColumnDefinitionsDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
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
    class datatable_class(Datatable):
        pub_date = columns.DateColumn("Publication date", sources=['get_pub_date'])

        class Meta:
            columns = ['blog', 'headline', 'pub_date']

    implementation = u"""
    class MyDatatable(Datatable):
        pub_date = columns.DateColumn("Publication date", sources=['get_pub_date'])

        class Meta:
            columns = ['blog', 'headline', 'pub_date']

    class ColumnBackedByMethodDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
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
    class datatable_class(Datatable):
        headline = columns.TextColumn("Headline", sources=['headline', 'blog__name'],
                                      processor='get_headline_data')
        class Meta:
            columns = ['id', 'headline']

        def get_headline_data(self, instance, **kwargs):
            return "%s (%s)" % (instance.headline, instance.blog.name)

    implementation = u"""
    class MyDatatable(Datatable):
        headline = columns.TextColumn("Headline", sources=['headline', 'blog__name'],
                                      processor='get_headline_data')
        class Meta:
            columns = ['id', 'headline']

        def get_headline_data(self, instance, **kwargs):
            return "%s (%s)" % (instance.headline, instance.blog.name)

    class CompoundColumnDatatableView(DatatableView):
        datatable_class = MyDatatable
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
    leverage this to avoid recalculating the same value from related lookups in your callbacks.
    """
    model = Entry
    class datatable_class(Datatable):
        blog_name = columns.TextColumn("Blog name", ["blog__name"])
        blog_id = columns.TextColumn("Blog ID", ["blog__id"])

        class Meta:
            columns = ['id', 'headline', 'blog_name', 'blog_id', 'pub_date']

    implementation = u"""
    class MyDatatable(Datatable):
        blog_name = columns.TextColumn("Blog name", ["blog__name"])
        blog_id = columns.TextColumn("Blog ID", ["blog__id"])

        class Meta:
            columns = ['id', 'headline', 'blog_name', 'blog_id', 'pub_date']

    class RelatedFieldsDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
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
    class datatable_class(Datatable):
        author_names_text = columns.TextColumn("Author Names", sources=['authors__name'], processor='get_author_names')
        author_names_links = columns.TextColumn("Author Links", sources=['authors__name'], processor='get_author_names_as_links')

        class Meta:
            columns = ['id', 'headline', 'author_names_text', 'author_names_links']

        def get_author_names(self, instance, *args, **kwargs):
            return ", ".join([author.name for author in instance.authors.all()])

        def get_author_names_as_links(self, instance, *args, **kwargs):
            return ", ".join([helpers.link_to_model(author) for author in instance.authors.all()])

    implementation = u"""
    class MyDatatable(Datatable):
        author_names_text = columns.TextColumn("Author Names", sources=['authors__name'], processor='get_author_names')
        author_names_links = columns.TextColumn("Author Links", sources=['authors__name'], processor='get_author_names_as_links')

        class Meta:
            columns = ['id', 'headline', 'author_names_text', 'author_names_links']

        def get_author_names(self, instance, *args, **kwargs):
            return ", ".join([author.name for author in instance.authors.all()])

        def get_author_names_as_links(self, instance, *args, **kwargs):
            from datatableview import helpers
            return ", ".join([helpers.link_to_model(author) for author in instance.authors.all()])

    class ManyToManyFields(DatatableView):
        model = Entry
        datatable_class = MyDatatable
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
    class datatable_class(Datatable):
        class Meta:
            columns = ['id', 'headline', 'body_text', 'blog', 'pub_date']

        def get_column_body_text_data(self, instance, *args, **kwargs):
            return instance.body_text[:30]

        def get_column_pub_date_data(self, instance, *args, **kwargs):
            return instance.pub_date.strftime("%m/%d/%Y")

    implementation = u"""
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline', 'body_text', 'blog', 'pub_date']

        def get_column_body_text_data(self, instance, *args, **kwargs):
            return instance.body_text[:30]

        def get_column_pub_date_data(self, instance, *args, **kwargs):
            return instance.pub_date.strftime("%m/%d/%Y")

    class DefaultCallbackNamesDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
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
    class datatable_class(Datatable):
        class Meta:
            columns = ['id', 'headline', 'blog', 'pub_date']
            processors = {
                'headline': helpers.make_xeditable,
                'blog': helpers.make_xeditable,
                'pub_date': helpers.make_xeditable,
            }

    implementation = u"""
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline', 'blog', 'pub_date']
            processors = {
                'headline': helpers.make_xeditable,
                'blog': helpers.make_xeditable,
                'pub_date': helpers.make_xeditable,
            }

    class XEditableColumnsDatatableView(XEditableDatatableView):
        model = Entry
        datatable_class = MyDatatable
    </pre>
    <pre class="brush: javascript">
    // Page javascript
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
    class datatable_class(Datatable):
        blog_name = columns.TextColumn("Blog name", sources=['blog__name'], processor=helpers.link_to_model)
        age = columns.TextColumn("Age", sources=['pub_date'], processor=helpers.through_filter(timesince))
        interaction = columns.IntegerColumn("Interaction", sources=['get_interaction_total'], processor=helpers.make_boolean_checkmark)

        class Meta:
            columns = ['id', 'blog_name', 'headline', 'body_text', 'pub_date', 'mod_date', 'age',
                       'interaction', 'n_comments', 'n_pingbacks']
            processors = {
                'id': helpers.link_to_model,
                'blog_name': helpers.link_to_model(key=lambda obj: obj.blog),
                'headline': helpers.make_xeditable,
                'body_text': helpers.itemgetter(slice(0, 30)),
                'pub_date': helpers.format_date('%A, %b %d, %Y'),
                'n_comments': helpers.format("{0:,}"),
                'n_pingbacks': helpers.format("{0:,}"),
            }

    implementation = u"""
    class MyDatatable(Datatable):
        class Meta:
            columns = [
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
            ]

    class HelpersReferenceDatatableView(XEditableDatatableView):
        model = Entry
        datatable_class = MyDatatable
    """


# Advanced topics
class PerRequestOptionsDatatableView(DemoMixin, DatatableView):
    """
    Care must be taken to modify the options object on the View class: because it is defined as a
    class attribute, there is only one copy of it in memory, and changing it is not thread safe.

    To safely change the options at runtime, always make sure to fully copy the data before making
    changes.  The simplest way to do this is via a call to the built-in ``copy.deepcopy`` function.
    """
    model = Entry
    class datatable_class(Datatable):
        class Meta:
            columns = [
                'id',
                'headline',
            ]

    def get_datatable_kwargs(self):
        from copy import deepcopy
        kwargs = super(PerRequestOptionsDatatableView, self).get_datatable_kwargs()
        columns_copy = deepcopy(self.datatable_class._meta.columns)
        columns_copy.append('blog')
        kwargs['columns'] = columns_copy
        return kwargs

    implementation = u"""
    class MyDatatable(Datatable):
        class Meta:
            columns = [
                'id',
                'headline',
            ]

    class PerRequestOptionsDatatableView(DemoMixin, DatatableView):
        model = Entry
        datatable_class = MyDatatable

        def get_datatable_kwargs(self):
            from copy import deepcopy
            kwargs = super(PerRequestOptionsDatatableView, self).get_datatable_kwargs()
            columns_copy = deepcopy(self.datatable_class._meta.columns)
            columns_copy.append('blog')
            kwargs['columns'] = columns_copy
            return kwargs
    """


class MultipleTablesDatatableView(DemoMixin, MultipleDatatableView):
    """
    ``MultipleDatatableView`` uses a slightly different configuration mechanism to allow the view to
    carry on it a dynamic set of Datatable classes that it will send to the context.  The primary
    feature of this version of the view is that it will dynamically route all AJAX requests to the
    correct datatable class, even though they are all living on the same URL.

    Another way to accomplish this effect would be to declare separate views and just pull their
    datatable specifications into the context of the one master view.  (See
    <a href="/embedded-table/">Embdeeded on another view</a> for an example of that pattern.)

    To get started, instead of declaring a ``datatable_class`` attribute on the view, you will
    instead declare a ``datatable_classes`` dict.  This is a map of names to classes.  These names
    will have ``"_datatable"`` added to the end when the datatable objects are added to the template
    rendering context.  Consequently, you do not need to declare the normal
    ``context_datatable_name`` setting on the view.

    This version of the view does not behave exactly like a ListView, specifically in the case of
    referencing the ``get_queryset()`` method you're accustomed to using.  Instead, you will need
    to declare methods that match each of the names you gave each class, such as
    ``get_FOO_datatable_queryset()``.

    If you need to modify the kwargs sent into the datatable class initialization, follow the same
    pattern: define a ``get_FOO_datatable_kwargs(**kwargs)`` method for any specific table that
    requires deviation from the default kwargs.

    WARNING:
    Declaring a custom kwargs getter like ``get_FOO_datatable_kwargs(**kwargs)`` will require you to
    manually grab a copy of the default kwargs via a call to
    ``get_default_datatable_kwargs(**kwargs)``, which is provided for you to use.  Think of this
    like a call to super().

    INFO:
    ``MultipleDatatableView`` does not support the configuration strategy where you declare options
    as class attributes on the view.  Having multiple datatables on the view makes this unwieldy.
    These settings are just kwargs that are sent to the Datatable object anyway, so if you would
    like to perform view-level manipulation of the settings sent to a Datatable, provide a
    ``get_FOO_datatable_kwargs(**kwargs)`` method using the instructions just above, and just put
    the settings in those kwargs to accomplish the same effect.

    In order to respond to AJAX queries, the view will modify the ``url`` value of each datatable to
    append a GET parameter hint in the format ``?datatable=FOO``, where FOO is the datatable name.
    This will cause queries that come back to the view to carry this hint so that it can
    transparently respond to the query with the right server-side Datatable object.

    Demo #1 in this series of examples is just a standard table with no fanciness added to it.
    Demo #2 shares the same Datatable options as demo #1, but slices off the ``"Header"`` column in
    a custom implementation of ``get_demo2_datatable_kwargs()``.  Demo #3 uses a separate Datatable
    object that targets a completely different model.
    """

    # Demo #1 and Demo # 2 will use variations of the same options.
    class datatable_class(Datatable):
        class Meta:
            columns = ['id', 'headline']

    # Demo #3 will use completely separate options.
    class blog_datatable_class(Datatable):
        class Meta:
            columns = ['id', 'name', 'tagline']

    datatable_classes = {
        'demo1': datatable_class,
        'demo2': datatable_class,
        'demo3': blog_datatable_class,
    }

    def get_demo1_datatable_queryset(self):
        return Entry.objects.all()

    def get_demo2_datatable_queryset(self):
        return Entry.objects.all()

    def get_demo3_datatable_queryset(self):
        return Blog.objects.all()

    def get_demo2_datatable_kwargs(self, **kwargs):
        kwargs = self.get_default_datatable_kwargs(**kwargs)
        kwargs['columns'] = self.datatable_class._meta.columns[1:]
        return kwargs

    implementation = u"""
    # Demo #1 and Demo #2 will use variations of the same options.
    class EntryDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline']

    # Demo #3 will use completely separate options.
    class BlogDatatable(Datatable):
        class Meta:
            columns = ['id', 'name', 'tagline']

    class MultipleTablesDatatableView(MultipleDatatableView):
        datatable_classes = {
            'demo1': EntryDatatable,
            'demo2': EntryDatatable,
            'demo3': BlogDatatable,
        }

        def get_demo1_datatable_queryset(self):
            return Entry.objects.all()

        def get_demo2_datatable_queryset(self):
            return Entry.objects.all()

        def get_demo3_datatable_queryset(self):
            return Blog.objects.all()

        def get_demo2_datatable_kwargs(self, **kwargs):
            kwargs = self.get_default_datatable_kwargs(**kwargs)
            kwargs['columns'] = EntryDatatable._meta.columns[1:]
            return kwargs
    """


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
        context['datatable'] = SatelliteDatatableView().get_datatable()
        return context

    implementation = u"""
    class EmbeddedTableDatatableView(TemplateView):
        def get_context_data(self, **kwargs):
            context = super(EmbeddedTableDatatableView, self).get_context_data(**kwargs)
            context['datatable'] = SatelliteDatatableView().get_datatable()
            return context

    class MyDatatable(Datatable):
        class Meta:
            columns = [
                'id',
                'headline',
                'pub_date',
            ]

    class SatelliteDatatableView(DatatableView):
        \"\"\"
        External view powering the embedded table for ``EmbeddedTableDatatableView``.
        \"\"\"
        model = Entry
        datatable_class = MyDatatable
    """


class SatelliteDatatableView(DatatableView):
    """
    External view powering the embedded table for ``EmbeddedTableDatatableView``.
    """
    template_name = "blank.html"
    model = Entry
    class datatable_class(Datatable):
        class Meta:
            columns = [
                'id',
                'headline',
                'pub_date',
            ]

    def get_datatable_kwargs(self):
        kwargs = super(SatelliteDatatableView, self).get_datatable_kwargs()
        kwargs['url'] = reverse('satellite')
        return kwargs


class SkippedRecordDatatableView(DemoMixin, DatatableView):
    """
    WARNING:
    Avoid this.

    Normally all queryset modification should happen at the view level, but it's possible that there
    is mixed or sophisticated items in the list that deserve to be omitted from the final list of
    objects.  Performing this work might be prohibitively expensive in a simple ``get_queryset()``
    implementation, where you don't yet have access to information about filters, pagination, etc.

    Experimental support for late omission of a record is available by raising
    ``datatableview.exceptions.SkipRecord`` anywhere in ``preload_record_data()`` or from inside a
    column processor function.  Upon encountering this exception, the loop will continue past the
    object without adding it to the final page output.

    WARNING:
    Pages that have removed arbitrary objects will exhibit a quirky numbering range that appears to
    include the dropped records.  The dataTables javascript is assuming that the page matches the
    requested length (unless it's the last page).  In this demo, the first page has only one record,
    and there are only a total of 5 total records, however the footer claims that it contains
    records <code>1 to 2 of 6</code>.<br><br>We've chosen not to decrement the 6 down to 5, because
    the total can only be monkey-patched for skips found on the current page; skipped records from
    other pages have no opportunity to be "removed" from the total count, since only the activate
    page is put through the serialization process where <code>SkipRecord</code> can be raised.
    """
    model = Entry
    class datatable_class(Datatable):
        class Meta:
            columns = ['id', 'headline', 'blog']
            page_length = 2

        def get_record_data(self, obj):
            if obj.pk == 1:
                raise SkipRecord
            return Datatable.get_record_data(self, obj)

    implementation = u"""
    from datatableview import SkipRecord
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline', 'blog']
            page_length = 2

        def get_record_data(self, obj):
            if obj.pk == 1:
                raise SkipRecord
            return super(MyDatatable, self).get_record_data(obj)

    class SkippedRecordDatatableView(DemoMixin, DatatableView):
        model = Entry
        datatable_class = MyDatatable
    """


# Template rendering
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
    class datatable_class(Datatable):
        class Meta:
            structure_template = "custom_table_template.html"
            columns = [
                'id',
                'headline',
                'blog',
                'pub_date',
            ]

    implementation = u"""
    class MyDatatable(Datatable):
        class Meta:
            structure_template = "custom_table_template.html"
            columns = [
                'id',
                'headline',
                'blog',
                'pub_date',
            ]

    class CustomizedTemplateDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
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
    are a little lackluster by comparison.  To fix this, reference the latest integration helper CSS
    and javascript support files in the template:

    <pre>
    &lt;link href="//cdn.datatables.net/plug-ins/be7019ee387/integration/bootstrap/3/dataTables.bootstrap.css" rel="stylesheet" /&gt;
    </pre>
    <pre>
    &lt;script src="//cdn.datatables.net/plug-ins/be7019ee387/integration/bootstrap/3/dataTables.bootstrap.js"&gt;&lt;/script&gt;
    </pre>

    See <a href="https://datatables.net/examples/styling/bootstrap.html">the official datatables
    documentation</a> on the subject for more information.

    WARNING:
    The pagination buttons are currently a bit strange with Bootstrap 3.1.1 and Datatables 1.10.0.
    Please make sure you are using the latest integration files by checking the link just above.
    """
    model = Entry
    class datatable_class(Datatable):
        class Meta:
            structure_template = "datatableview/bootstrap_structure.html",
            columns = [
                'id',
                'headline',
                'blog',
                'pub_date',
            ]

    implementation = u"""
    class MyDatatable(Datatable):
        class Meta:
            structure_template = "datatableview/bootstrap_structure.html",
            columns = [
                'id',
                'headline',
                'blog',
                'pub_date',
            ]

    class BootstrapTemplateOfficialDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
    """


class CSSStylingDatatableView(DemoMixin, DatatableView):
    """
    The default template used by the datatable context variable when you render it will include
    ``data-name`` attributes on the ``&lt;th&gt;`` column headers, which is the ``slugify``'d
    version of the column's label.  This makes sizing the columns very easy.
    """
    model = Entry
    class datatable_class(Datatable):
        class Meta:
            columns = [
                'id',
                'headline',
                'blog',
                ("Publication date", 'pub_date'),
            ]

    implementation = u"""
    class MyDatatable(Datatable):
        class Meta:
            columns = [
                'id',
                'headline',
                'blog',
                ("Publication date", 'pub_date'),
            ]

    class CSSStylingDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
    """


