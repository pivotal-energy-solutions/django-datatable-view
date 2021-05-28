# -*- coding: utf-8 -*-

from os import sep
import os.path
import re
import django
from django.urls import reverse
from django.views.generic import View, TemplateView
from django.template.defaultfilters import timesince

import datatableview
from datatableview import Datatable, ValuesDatatable, columns, SkipRecord
from datatableview.views import DatatableView, MultipleDatatableView, XEditableDatatableView
from datatableview.views.legacy import LegacyDatatableView
from datatableview import helpers

from .models import Entry, Blog


class ResetView(View):
    """Google App Engine view for reloading the database to a fresh state every 24 hours."""

    def get(self, request, *args, **kwargs):
        from django.core.management import call_command
        from django.http import HttpResponse

        call_command("syncdb")
        call_command("loaddata", "initial_data.json")
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
        context["db_works"] = db_works

        path, working_directory = os.path.split(os.path.abspath("."))
        context["working_directory"] = working_directory
        context["os_sep"] = sep

        # Versions
        context.update(
            {
                "datatableview_version": ".".join(map(str, datatableview.__version_info__)),
                "django_version": django.get_version(),
                "datatables_version": "1.10.9",
            }
        )

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
        """Try the view's snake_case name, or else use default simple template."""
        name = self.__class__.__name__.replace("DatatableView", "")
        name = re.sub(r"([a-z]|[A-Z]+)(?=[A-Z])", r"\1_", name)
        return ["demos/" + name.lower() + ".html", "example_base.html"]

    def get_context_data(self, **kwargs):
        context = super(DemoMixin, self).get_context_data(**kwargs)
        context["implementation"] = self.implementation

        # Unwrap the lines of description text so that they don't linebreak funny after being put
        # through the ``linebreaks`` template filter.
        alert_types = ["info", "warning", "danger"]
        paragraphs = []
        p = []
        alert = False
        for line in self.__doc__.splitlines():
            line = line[4:].rstrip()
            if not line:
                if alert:
                    p.append("""</div>""")
                    alert = False
                paragraphs.append(p)
                p = []
            elif line.lower()[:-1] in alert_types:
                p.append("""<div class="alert alert-{type}">""".format(type=line.lower()[:-1]))
                alert = True
            else:
                p.append(line)
        description = "\n\n".join(" ".join(p) for p in paragraphs)
        context["description"] = re.sub(r"``(.*?)``", r"<code>\1</code>", description)

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
            columns = ["id", "headline", "pub_date", "n_comments", "n_pingbacks"]
            ordering = ["-id"]
            page_length = 5
            search_fields = ["blog__name"]
            unsortable_columns = ["n_comments"]
            hidden_columns = ["n_pingbacks"]
            structure_template = "datatableview/default_structure.html"

    implementation = """
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
    <li>``object_list`` is a QuerySet, not just a python list.</li>
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
    processor callbacks in the above demo.  Notice that it has keys for all ORM source names mixed
    with actual column names given by the configuration Datatable object:
    """

    model = Entry

    class datatable_class(ValuesDatatable):
        blog = columns.CompoundColumn("Blog", sources=["blog__id", "blog__name"])
        publication_date = columns.DateColumn("Publication Date", sources=["pub_date"])

        class Meta:
            model = Entry
            columns = ["id", "blog", "headline", "publication_date", "n_comments", "n_pingbacks"]

    implementation = """
    class MyDatatable(ValuesDatatable):
        blog = columns.CompoundColumn("Blog", sources=['blog__id', 'blog__name'])
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
    attributes and automatically construct a plain Datatable object to power the view if one is not
    already given.

    All of the available settings can be given in this format, and can even be combined with a
    ``datatable_class`` configuration object.  Attributes on the view will override the settings
    from a Datatable instance during instantiation, which makes simple tweaks to generic Datatable
    objects very easy.
    """

    model = Entry
    columns = ["id", "headline", "pub_date"]

    implementation = """
    # Specifying Datatable.Meta options directly on the view
    class ConfigureInlineDatatableView(DatatableView):
        model = Entry
        columns = ['id', 'headline', 'pub_date']


    # View attributes will override Datatable.Meta settings if they conflict
    class MyDatatable(Datatable):
        class Meta:
            columns = ['headline']
    class ConfigureCombinedDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
        columns = ['id', 'headline', 'pub_date']
    """


class ConfigureDatatableOptions(DemoMixin, LegacyDatatableView):
    """
    WARNING:
    Avoid using this configuration strategy, as it will be removed in the 1.0 release.

    Before version 0.9, the configuration strategy resembled that of the inline style using the
    view's class attributes, except that all of the available settings were put inside of one
    dictionary called ``datatable_options``.

    Use ``datatableview.views.legacy.LegacyDatatableView`` to allow your ``datatable_options`` dict
    to be discovered and converted to the modern syntax on the fly.
    """

    model = Entry
    datatable_options = {
        "columns": [
            "id",
            ("Publication Date", "pub_date"),
            "headline",
        ],
    }

    implementation = """
    from datatableview.views.legacy import LegacyDatatableView
    class LegacyConfigDatatableView(LegacyDatatableView):
        model = Entry
        datatable_options = {
            'columns': ['id', ("Publication Date", 'pub_date'), 'headline'],
        }
    """


# Column configurations
class ZeroConfigurationDatatableView(DemoMixin, DatatableView):
    """
    If no columns are specified by the view's ``Datatable`` configuration object (or no
    ``datatable_class`` is given at all), ``DatatableView`` will use all of the model's local
    fields.  Note that this does not include reverse relationships, many-to-many fields (even if the
    ``ManyToManyField`` is defined on the model directly), nor the special ``pk`` field, but DOES
    include ``ForeignKey`` fields defined directly on the model.

    Note that fields will automatically use their ``verbose_name`` for the frontend table headers.

    WARNING:
    When no columns list is explicitly given, the table will end up trying to show foreign keys as
    columns, generating at least one extra query per displayed row.  Implement a ``get_queryset()``
    method on your view that returns a queryset with the appropriate call to ``select_related()``.
    """

    model = Entry

    implementation = """
    class ZeroConfigurationDatatableView(DatatableView):
        model = Entry
    """


class SpecificColumnsDatatableView(DemoMixin, DatatableView):
    """
    To target specific columns that should appear on the table, use the ``columns`` configuration
    option.  Specify a tuple or list of model field names, in the order that they are to appear on
    the table.

    Items in the columns list can name either a model field directly, or a custom column defined
    locally on the ``Datatable`` object (which can be a customized version of a model field, or a
    virtual field that is supplying a value via a model property or method).  See
    <a href="/related-column-definitions/">Related field columns</a>,
    <a href="/virtual-column-definitions/">Non-field columns</a> and
    <a href="/column-backed-by-method/">Model method-backed columns</a> for help defining custom
    columns.

    Note that fields will use their ``verbose_name`` when the named field is a simple model field.
    """

    model = Entry

    class datatable_class(Datatable):
        class Meta:
            columns = ["id", "headline", "blog", "pub_date"]

    implementation = """
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline', 'blog', 'pub_date']

    class SpecificColumnsDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
    """


class PrettyNamesDatatableView(DemoMixin, DatatableView):
    """
    As with the Django forms framework, verbose names can be given or overridden via the ``labels``
    configuration option, which is a dict mapping the column name to the desired string.  In this
    example, the ``pub_date`` field has been given the label ``"Publication date"``.
    """

    model = Entry

    class datatable_class(Datatable):
        class Meta:
            columns = ["blog", "headline", "pub_date", "n_comments", "rating"]
            labels = {
                "pub_date": "Publication date",
            }

    implementation = """
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


class CustomColumnsDatatableView(DemoMixin, DatatableView):
    """
    As in the Django forms framework, extra columns can be added to a ``Datatable`` by defining them
    directly on the class, and then adding that column's name into the Meta ``columns`` list.  (With
    built-in forms, Django doesn't force you to name the extra field in the Meta list of fields, but
    we prefer to make you add the column name to the full ``columns`` list to ensure the order is
    good.)

    The various parts of a column definition can be given within Meta as dictionaries (see
    <a href="/pretty-names/">Custom verbose names</a>, for example), but of course a column can be
    defined explicitly all in one go.

    INFO:
    See the <a href="columns-reference">``columns`` reference</a> page for the full list of
    ``Column`` classes available for use.

    When a column is virtual (computed), <a href="/compound-columns/">compound</a>, or requires a
    specifically chosen ``Column`` type, the column should be declared in explicit syntax.

    The arguments to a ``Column`` are the verbose name for the column header, the ``sources`` list
    of model fields/methods/properties that power the column's data, and optionally a ``processor``.

    The ``sources`` list can name fields that span model relationships via the traditional ``"__"``
    syntax.  The "Blog" column does this to retrieve the ``entry.blog.name`` value.

    Some columns may need to represent a value that is be entirely computed.  In this situation, the
    column's ``sources`` list can be given as ``None``, handing all of the work to data retrieval to
    the ``processor`` callback.  The processor will receive the object instance, allowing it to
    return whatever arbitrary data the column needs to display.

    INFO:
    If the ``sources`` is ``[]`` or ``None``, ``sortable=False`` is automatically implied. If you
    need sorting, consider splitting up the work that you intend to do with the ``processor``, so
    that there is a field, method, or property that can be used as the source, and the processor
    just manipulates that value. This will at least provide you with in-memory sorting of the core
    value.

    INFO:
    In this particular example, the better approach might simply be to give ``['pub_date']`` as the
    ``sources`` list, but it was omitted specifically to demonstrate the bridging of the gap by the
    callback.

    INFO:
    Columns without ``sources`` can be explicitly defined with ``DisplayColumn`` instead of one of
    the usual column types.

    WARNING:
    Columns without ``sources`` cannot be searched or sorted. Even if your processor function were
    to return a simple model field value, the Datatable lacks the necessary hints to know this.
    Always give ``sources`` where they exist.

    See <a href="/processors/">Postprocessing values</a> for more information on processor
    functions.
    """

    model = Entry

    class datatable_class(Datatable):
        blog = columns.TextColumn("Blog", sources=["blog__name"])
        age = columns.TextColumn("Age", sources=None, processor="get_entry_age")

        class Meta:
            columns = ["blog", "headline", "age"]

        def get_entry_age(self, instance, **kwargs):
            return timesince(instance.pub_date)

    implementation = """
    from django.template.defaultfilters import timesince

    class MyDatatable(Datatable):
        blog = columns.TextColumn("Blog", sources=['blog__name'])
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
    Model methods and properties can also be given in a column's ``sources`` list, not just real
    model field names.  If the source is resolved on the model to be a callable method, it will be
    called with no arguments to obtain the real value.

    INFO:
    Because methods and properties aren't actual model fields, these sources won't be able to
    contribute to database sorting and filtering.  The same effect would be acheived by using
    ``sources=None`` and ``processor='some_callback'``, where the ``some_callback`` function simply
    called the object method on its own.

    In this situation, the ``pub_date`` is fetched using a hypothetical model method
    ``get_pub_date()``, which is why it is not given on the datatable definition.

    This strategy is convenient for fields that have a ``choices`` list, allowing you to use the
    ``get_FOO_display()`` method Django puts on the model instance.
    """

    model = Entry

    class datatable_class(Datatable):
        pub_date = columns.DateColumn("Publication date", sources=["get_pub_date"])

        class Meta:
            columns = ["blog", "headline", "pub_date"]

    implementation = """
    class MyDatatable(Datatable):
        pub_date = columns.DateColumn("Publication date", sources=['get_pub_date'])

        class Meta:
            columns = ['blog', 'headline', 'pub_date']

    class ColumnBackedByMethodDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
    """


class ProcessorsDatatableView(DemoMixin, DatatableView):
    """
    After the column data is fetched from the database, but before it is serialized to JSON, each
    column can be sent to a processor callback.

    The processor can be given as a string or as a direct reference.  If the processor is a string,
    the ``Datatable`` (or the orignating ``DatatableView``) should have a method with that name.

    As is the trend with the Django forms framework, a ``processors`` configuration dict can be
    given to provide processors for columns that aren't being explicitly constructed on the
    Datatable.

    INFO:
    Processors receive the ``instance`` object that is providing data for the current row, and
    should somehow return the final string that should be serialized to JSON for the AJAX response
    to the client.

    INFO:
    Processors should also always receive ``**kwargs``, to maximize forward compatibility with how
    processors are called.  There are a few internal references provided by default that help the
    default global processor to do the right thing, but the typical processor function shouldn't
    need to concern itself with those values.

    This example actually uses the same column twice; the first time is for a raw display of the
    ``pub_date`` value, and the second is for an "Age" column, representing the same original data,
    but sent through the template filter ``timesince``.

    Note that the ``Age`` column is sortable and searchable based on the ``sources`` list, which is
    ``pub_date`` in this example.  We avoid sorting the presentionally modified text because of the
    performance implications of processing every row in the entire database table in order to sort
    and show only one page of results.
    """

    model = Entry

    class datatable_class(Datatable):
        age = columns.TextColumn("Age", sources=["pub_date"], processor="get_entry_age")

        class Meta:
            columns = ["blog", "headline", "pub_date", "age"]
            processors = {
                "pub_date": "format_pub_date",
            }

        def format_pub_date(self, instance, **kwargs):
            return instance.pub_date.strftime("%m/%d/%Y")

        def get_entry_age(self, instance, **kwargs):
            return timesince(instance.pub_date)

    implementation = """
    from django.template.defaultfilters import timesince

    class MyDatatable(Datatable):
        age = columns.TextColumn("Age", sources=['pub_date'], processor='get_entry_age')

        class Meta:
            columns = ['blog', 'headline', 'pub_date', 'age']
            processors = {
                'pub_date': 'format_pub_date',
            }

        def format_pub_date(self, instance, **kwargs):
            return instance.pub_date.strftime("%m/%d/%Y")

        def get_entry_age(self, instance, **kwargs):
            return timesince(instance.pub_date)

    class PresentationalChangesDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
    """


class CompoundColumnsDatatableView(DemoMixin, DatatableView):
    """
    Simple columns only need one model field to represent their data, even when marked up by a
    processor function.  However, if a column actually represents more than one model field the
    list of those fields can be given in place of a single field name.  For example, an address
    might be composed of multiple model fields working together to display a more complicated
    string.  Each model field involved should be listed as a source.

    INFO:
    You'll probably want to provide a custom ``processor`` function in order to decide how these
    values should be rendered.  Without one, the default strategy is to join the various source
    values with ``" "``.  The utility of this is limited, but it's a reasonable default to give you
    a starting point.

    Compound columns should target the individual fields, not merely the foreign key itself.  For
    example, you might indeed want the ``str(entry.blog)`` representation to appear in the
    marked-up column data, but be sure to target the specific fields (such as ``blog__name``) that
    are actually being represented in that display.  Putting just ``blog`` as a source would imply
    that the user would search on the ``blog.pk`` value, which is information that is not
    necessarily available for them to know, and would certain create unpredictable sorting behavior.

    Specifying all of the relevant fields in a compound column helps make searching and sorting more
    natural.  Sorting a compound column is the same as giving the sources list to the queryset
    ``order_by()`` method (with non-db sources stripped from the list, such as method and property
    names).

    There is a special ``CompoundColumn`` class for representing completely different data types in
    a single column.  In many situations, you don't actually need to worry about this distinction,
    because sources are automatically treated appropriately based on what kind of model field they
    represent.  (The mechanism used here is the same as when ``Meta.columns`` names model fields to
    import to the ``Datatable`` without explicitly stating which column class to use.)  However, it
    is strongly recommended that if the data types are mixed you should use ``CompoundColumn``
    instead of choosing some arbitrary other column to wrap them.

    ``CompoundColumn`` actually uses other ``Column`` instances as its sources rather than just
    names of those sources. In turn, these nested columns point at the sources they control.
    You will divide up the sources based on the specific column class they use.

    INFO:
    Columns nested within a ``CompoundColumn`` don't need labels, because they don't actually get
    rendered to the client.  It is purely a server-side mechanism that separates the handlers for
    different data types.

    INFO:
    If you find yourself making a ``CompoundColumn`` with only one type of ``Column`` inside of it,
    you probably don't need to use ``CompoundColumn``.

    In addition to specifying column types for different groups of source types, this enables the
    use of custom, non-registered ``Column`` subclasses.  Such classes might not be suitable for
    general registration for automatic assignment to as model field handlers, but can be used
    directly when you see fit.
    """

    model = Entry

    class datatable_class(Datatable):
        headline_blog = columns.TextColumn(
            "Headline (Blog)",
            sources=["headline", "blog__name"],
            processor=helpers.format("{0[0]} ({0[1]})"),
        )
        headline_pub = columns.CompoundColumn(
            "Headline (Published)",
            sources=[columns.TextColumn(source="headline"), columns.DateColumn(source="pub_date")],
            processor=helpers.format("{0[0]} @ {0[1]}"),
        )

        class Meta:
            columns = ["id", "headline_blog", "headline_pub"]

    implementation = """
    class MyDatatable(Datatable):
        headline = columns.TextColumn("Headline", sources=['headline', 'blog__name'],
                                      processor='get_headline_data')
        headline = columns.CompoundColumn("Headline", sources=[
                       columns.TextColumn(source='headline'),
                       columns.TextColumn(source='blog__name'),
                   ], processor='get_headline_data')
        class Meta:
            columns = ['id', 'headline']

        def get_headline_data(self, instance, **kwargs):
            return "%s (%s)" % (instance.headline, instance.blog.name)

    class CompoundColumnDatatableView(DatatableView):
        datatable_class = MyDatatable
    """


class ManyToManyFieldsDatatableView(DemoMixin, DatatableView):
    """
    ``ManyToManyField`` relationships should not be specified directly as the column's only field in
    the ``sources`` list.

    The most straightforward way to reveal a plural set of objects is to create your own processor
    that handles each item in the object list as you see fit.  For example, combined with the
    ``helpers`` module, you can quickly make links out of the objects in the relationship.

    In this demo, we are pointing the ``sources`` list at the ``"authors__name"`` field, because
    that is the only visible data we are displaying in each column.  The ``processor`` callback
    receives the actual row instance and can look up the full authors queryset (including pk for use
    in url ``reverse()``).
    """

    model = Entry

    class datatable_class(Datatable):
        author_names_text = columns.TextColumn(
            "Author Names", sources=["authors__name"], processor="get_author_names"
        )
        author_names_links = columns.TextColumn(
            "Author Links", sources=["authors__name"], processor="get_author_names_as_links"
        )

        class Meta:
            columns = ["id", "headline", "author_names_text", "author_names_links"]

        def get_author_names(self, instance, *args, **kwargs):
            return ", ".join([author.name for author in instance.authors.all()])

        def get_author_names_as_links(self, instance, *args, **kwargs):
            return ", ".join([helpers.link_to_model(author) for author in instance.authors.all()])

    implementation = """
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


class DefaultCallbackNamesDatatableView(DemoMixin, LegacyDatatableView):
    """
    WARNING:
    Implicit callbacks are a concept from version 0.8 and earlier.  The example here is shown using
    legacy syntax because that is what it applies to.  All modern implementations using the
    ``Datatable`` object must explicitly name their ``processor`` functions.

    If a column definition hasn't supplied an explicit callback value processor, there is a default
    method that will be looked up on the view instance in the format of ``get_column_FOO_data()``.

    If the field has defined a "pretty name" in the tuple format, the pretty name will be used for
    the basis of looking up this default callback.  This is to avoid the complexities of mangling an
    automatic name that makes sense for compound and virtual columns.

    "Pretty names" put through the mangling process essentially normalize non-letter non-number
    characters to underscores, and multiple adjacent underscores are collapsed to a single
    underscore.  It's like a slugify process, but using ``"_"``, and without lowercasing.

    If the name mangling is ever unintuitive or cumbersome to remember or guess, you can either
    supply your own callback names as the third item in a column's 3-tuple definition, or else
    define a callback using the 0-based index instead of the field name, such as
    ``get_column_0_data()``.

    INFO:
    The implicit callbacks are only executed if there is no callback already supplied in the column
    definition (which is the way we recommend doing things).
    """

    model = Entry
    datatable_options = {
        "columns": ["id", "headline", "body_text", "blog", "pub_date"],
    }

    def get_column_body_text_data(self, instance, *args, **kwargs):
        return instance.body_text[:30]

    def get_column_pub_date_data(self, instance, *args, **kwargs):
        return instance.pub_date.strftime("%m/%d/%Y")

    implementation = """
    class DefaultCallbackNamesDatatableView(DatatableView):
        model = Entry

        datatable_options = {
            'columns': ['id', 'headline', 'body_text', 'blog', 'pub_date'],
        }

        def get_column_body_text_data(self, instance, *args, **kwargs):
            return instance.body_text[:30]

        def get_column_pub_date_data(self, instance, *args, **kwargs):
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

    class datatable_class(Datatable):
        class Meta:
            columns = ["id", "headline", "blog", "status", "pub_date"]
            processors = {
                "headline": helpers.make_xeditable,
                "blog": helpers.make_xeditable,
                "status": helpers.make_xeditable,
                "pub_date": helpers.make_xeditable,
            }

    implementation = """
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline', 'blog', 'status', 'pub_date']
            processors = {
                'headline': helpers.make_xeditable,
                'blog': helpers.make_xeditable,
                'status': helpers.make_xeditable,
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


class ColumnsReferenceDatatableView(DemoMixin, DatatableView):
    """
    ``Column`` classes handle the rendering of a value into a JSON-ready value, and are responsible
    for responding to search and sort queries on itself, so it is still important to match model
    fields up to their correct Column counterparts for accurate filter capabilities.

    Adding new custom subclasses is a simple matter of defining your own Column and declaring on it
    the ``model_field_class`` that it corresponds to.  Your custom column class will automatically
    be added to the registry that maps your new column to the model field it handles, and when a
    Datatable encounters a model field of the custom type, it will use your custom column class to
    handle it.

    The simplest custom column class just defines ``model_field_class`` as the model field it wants
    to represent, and provides any ``lookup_types`` that the query language supports for that field
    when searching for equality.

    See the
    <a href="http://django-datatable-view.readthedocs.org/en/latest/datatableview/columns.html">
    module documentation for columns</a> for more information.
    """

    model = Entry
    datatable_class = None
    implementation = """"""


class HelpersReferenceDatatableView(DemoMixin, XEditableDatatableView):
    """
    ``datatableview.helpers`` is a module decimated to functions that can be supplied directly as
    column callback functions.  Some of them are easy to use at runtime in your own callbacks,
    making some work easier for you, but the majority aim to solve common problems with as little
    fuss as possible.
    """

    model = Entry

    class datatable_class(Datatable):
        blog_name = columns.TextColumn(
            "Blog name", sources=["blog__name"], processor=helpers.link_to_model
        )
        age = columns.TextColumn(
            "Age", sources=["pub_date"], processor=helpers.through_filter(timesince)
        )
        interaction = columns.IntegerColumn(
            "Interaction",
            sources=["get_interaction_total"],
            processor=helpers.make_boolean_checkmark,
        )

        class Meta:
            columns = [
                "id",
                "blog_name",
                "headline",
                "body_text",
                "pub_date",
                "mod_date",
                "age",
                "interaction",
                "n_comments",
                "n_pingbacks",
            ]
            processors = {
                "id": helpers.link_to_model,
                "blog_name": helpers.link_to_model(key=lambda obj: obj.blog),
                "headline": helpers.make_xeditable,
                "body_text": helpers.itemgetter(slice(0, 30)),
                "pub_date": helpers.format_date("%A, %b %d, %Y"),
                "n_comments": helpers.format("{0:,}"),
                "n_pingbacks": helpers.format("{0:,}"),
            }

    implementation = """
    class MyDatatable(Datatable):
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

    class HelpersReferenceDatatableView(XEditableDatatableView):
        model = Entry
        datatable_class = MyDatatable
    """


# Advanced topics
class PerRequestOptionsDatatableView(DemoMixin, DatatableView):
    """
    When a ``DatatableView`` is run, it builds the ``Datatable`` configuration object from the
    information is has available about it.  In most cases, you will have supplied a simple
    ``datatable_class`` which packages all of the configuration for you.

    To modify this configuration per-request, treat the ``Datatable`` object like a form; by
    overriding the ``Datatable.__init__()`` method, you can add or remove items in the ``columns``
    dictionary, which behaves the way a form's ``fields`` dictionary does.

    INFO:
    Remember that the ``Meta.exclude`` list controls field exclusion for columns created from the
    source model.  You cannot exclude a column that you explicitly declared on the ``Datatable``
    class. You must remove it from the instance's ``columns`` dictionary. You can either send the
    necessary kwargs to make a runtime decision to the ``Datatable`` constructor by overriding the
    view's ``get_datatable_kwargs()`` method, or you can override the view's ``get_datatable()``
    method directly and modify the object that comes back from ``super()``.

    """

    model = Entry

    class datatable_class(Datatable):
        class Meta:
            columns = ["id", "headline"]

    def get_datatable(self):
        datatable = super(PerRequestOptionsDatatableView, self).get_datatable()
        datatable.columns["blog"] = columns.TextColumn("Blog Name", sources=["blog__name"])
        del datatable.columns["id"]
        return datatable

    implementation = """
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline']

    class PerRequestOptionsDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable

        def get_datatable(self):
            datatable = super(PerRequestOptionsDatatableView, self).get_datatable()
            datatable['blog'] = columns.TextColumn("Blog Name", sources=['blog__name'])
            del datatable['id']
            return datatable
    """


class RequestMethodDatatableView(DemoMixin, DatatableView):
    """
    Use the ``Meta.request_method`` option to change the ajax request type from ``GET`` to ``POST``.
    The view will adjust accordingly when responding to ajax queries.

    INFO:
    When using POST, Django's CSRF token is read from the cookie and sent as a header.  If you get
    unexpected HTTP 403 errors, confirm that the cookie is correctly set by using Django's
    ``@ensure_csrf_cookie`` decorator on the method.
    """

    model = Entry

    class datatable_class(Datatable):
        class Meta:
            columns = ["id", "headline"]
            request_method = "POST"

    implementation = """
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline']
            request_method = 'POST'

    class PerRequestOptionsDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
    """


class CustomModelFieldsDatatableView(DemoMixin, DatatableView):
    """ """

    model = Entry

    class datatable_class(Datatable):
        class Meta:
            columns = ["headline"]

    implementation = """"""


class HeadlineColumn(columns.TextColumn):
    model_field_class = None

    def search(self, model, term):
        from django.db.models import Q

        return Q(headline__startswith=term)


class CustomColumnQueriesDatatableView(DemoMixin, DatatableView):
    """
    Columns that need fine tuning of the search query have the option to subclass the appropriate
    ``Column`` class, such as ``TextColumn``, and override the ``search()`` method, as shown in the
    implementation example.

    If you call ``super()`` to get normal behavior, you will always receive a single ``Q`` instance
    that already has all of the compiled behavior for the given search term.  You can
    combine this object with new ``Q`` objects with bitwise operators like ``|``, ``&``, and ``~``
    to get a new single object to return.

    Of course, you can avoid calling ``super()`` at all, and just build a ``Q`` object from scratch.

    In this example, we're ignoring the default search behavior and doing something else: we build a
    ``Q`` object that only checks if the headline starts with the search term.

    INFO:
    The ``search()`` method receives a ``term`` that it should build a query around, but if the user
    searches multiple words separated by spaces, those terms will be sent to this method one at a
    time (unless the user explicitly searched for ``"two words"`` with quotes around them).

    WARNING:
    The ``term`` that is sent to the search method is pretty raw.  Be careful not to perform invalid
    queries with the term you are given.  The default implementation uses the ``model`` argument to
    decide which of the column's sources are database-backed, and then inspects those sources to
    find out what data types they represent, and spends some effort to coerce the term to fit.
    """

    model = Entry

    class datatable_class(Datatable):
        headline = HeadlineColumn("Headline", sources=["headline"])

        class Meta:
            columns = ["id", "headline"]

    implementation = """
    from django.db.models import Q
    from datatableview import columns

    class HeadlineColumn(columns.TextColumn):
        def search(self, model, term):
            return Q(headline__startswith=term)

    class MyDatatable(Datatable):
        headline = HeadlineColumn("Headline", sources=['headline'])
        class Meta:
            columns = ['id', 'headline']
    """


class ChoicesFieldsDatatableView(DemoMixin, DatatableView):
    """
    Fields with choices are of course just normal model fields, so by default queries against the
    column would be run for the database value part of the choice, not the label.

    However, choice fields are automatically detected and if the user searches for a string which
    happens to match a choice's label (case-insensitive), the column's search method will flip that
    search term into the appropriate database value and run that search instead.

    In the demo above, the raw ``status`` column ends up showing the raw value of course, but we've
    added an extra column "Status Display" which draws on the automatic Django-supplied method
    ``get_status_display()`` to show the label.

    INFO:
    Note that the ``status_display`` column we defined is not using a database-backed source, so
    searches are not being run against it directly.  The reason a search for ``'published'`` matches
    anything is because the ``status`` column is deciding that the search string can be found in one
    of its labels.  Running a search for the raw value actually listed in the column is still a
    valid query.
    """

    model = Entry

    class datatable_class(Datatable):
        status_display = columns.TextColumn("Status Display", sources=["get_status_display"])

        class Meta:
            columns = ["id", "headline", "status", "status_display", "is_published"]
            labels = {
                "status": "Status Value",
            }

    implementation = """
    class MyDatatable(Datatable):
        status_display = columns.TextColumn("Status Display", sources=['get_status_display'])

        class Meta:
            columns = ['id', 'headline', 'status', 'status_display', 'is_published']
            labels = {
                'status': "Status Value",
            }

    class ChoicesFieldsDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
    """


class MultipleTablesDatatableView(DemoMixin, MultipleDatatableView):
    """
    ``MultipleDatatableView`` uses a slightly different configuration mechanism to allow the view to
    carry on it a dynamic set of Datatable classes that it will send to the context.  The primary
    feature of this version of the view is that it will dynamically route all AJAX requests to the
    correct datatable class, even though they are all living on the same URL.

    Another way to accomplish this effect would be to declare separate views and just pull their
    datatable specifications into the context of the one master view.  (See
    <a href="/embedded-table/">Embdedded on another view</a> for an example of that pattern.)

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
    You can't call ``super()`` in ``get_FOO_datatable_kwargs(**kwargs)`` to get the default set of
    ``kwargs``, so they are provided to you automatically via ``**kwargs`` sent to the method.

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
            model = Entry
            columns = ["id", "headline"]

    # Demo #3 will use completely separate options.
    class blog_datatable_class(Datatable):
        class Meta:
            model = Blog
            columns = ["id", "name", "tagline"]

    datatable_classes = {
        "demo1": datatable_class,
        "demo2": datatable_class,
        "demo3": blog_datatable_class,
    }

    def get_demo1_datatable_queryset(self):
        return Entry.objects.all()

    def get_demo2_datatable_queryset(self):
        return Entry.objects.all()

    def get_demo3_datatable_queryset(self):
        return Blog.objects.all()

    def get_datatables(self, only=None):
        datatables = super(MultipleTablesDatatableView, self).get_datatables(only)
        if only in (None, "demo2"):
            demo2 = datatables["demo2"]
            del demo2.columns["id"]
        return datatables

    implementation = """
    # Demo #1 and Demo #2 will use variations of the same options.
    class EntryDatatable(Datatable):
        class Meta:
            model = Entry
            columns = ['id', 'headline']

    # Demo #3 will use completely separate options.
    class BlogDatatable(Datatable):
        class Meta:
            model = Blog
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

        def get_datatables(self, only=None):
            datatables = super(MultipleTablesDatatableView, self).get_datatables(only)
            if only in (None, 'demo2'):
                demo2 = datatables['demo2']
                del demo2.columns['id']
            return datatables
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
    the options object via its ``get_datatable()`` method.
    """

    def get_context_data(self, **kwargs):
        context = super(EmbeddedTableDatatableView, self).get_context_data(**kwargs)
        context["datatable"] = SatelliteDatatableView().get_datatable()
        return context

    implementation = """
    class EmbeddedTableDatatableView(TemplateView):
        def get_context_data(self, **kwargs):
            context = super(EmbeddedTableDatatableView, self).get_context_data(**kwargs)
            context['datatable'] = SatelliteDatatableView().get_datatable()
            return context

    class SatelliteDatatableView(DatatableView):
        \"\"\"
        External view powering the embedded table for ``EmbeddedTableDatatableView``.
        \"\"\"
        template_name = "blank.html"
        model = Entry
        class datatable_class(Datatable):
            class Meta:
                columns = ['id', 'headline', 'pub_date']

        def get_datatable_kwargs(self):
            kwargs = super(SatelliteDatatableView, self).get_datatable_kwargs()
            kwargs['url'] = reverse('satellite')
            return kwargs
    """


class SatelliteDatatableView(DatatableView):
    """
    External view powering the embedded table for ``EmbeddedTableDatatableView``.
    """

    template_name = "blank.html"
    model = Entry

    class datatable_class(Datatable):
        class Meta:
            columns = ["id", "headline", "pub_date"]

    def get_datatable_kwargs(self):
        kwargs = super(SatelliteDatatableView, self).get_datatable_kwargs()
        kwargs["url"] = reverse("satellite")
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
            columns = ["id", "headline", "blog"]
            page_length = 2

        def get_record_data(self, obj):
            if obj.pk == 1:
                raise SkipRecord
            return Datatable.get_record_data(self, obj)

    implementation = """
    from datatableview import SkipRecord
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline', 'blog']
            page_length = 2

        def get_record_data(self, obj):
            if obj.pk == 1:
                raise SkipRecord
            return super(MyDatatable, self).get_record_data(obj)

    class SkippedRecordDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
    """


# Extension support
class ColReorderDatatableView(DemoMixin, DatatableView):
    """
    The official <a href="https://datatables.net/extensions/colreorder/">``ColReorder``
    extension</a> is easy to add to any existing table.  To use it, make sure you include the
    appropriate javascript source file, and then use the ``R`` character in your ``sDom`` setting.

    To reorder columns, drag the header onto one of the other header labels to see them shift.

    INFO:
    The ``sDom`` setting you see in most examples that add this plugin is ``'Rlfrtip'``.
    """

    model = Entry

    class datatable_class(Datatable):
        blog = columns.TextColumn("Blog", sources=["blog__name"])

        class Meta:
            columns = ["headline", "blog"]

    implementation = """dummy"""  # don't hide the block, overridden in template


class MultiFilterDatatableView(DemoMixin, DatatableView):
    """
    The official <a href="http://datatables.net/examples/api/multi_filter.html">per-column
    searching</a> API is supported on the server if you can arrange for your client table to display
    the required filter widgets.

    The default datatable rendering template uses the Meta setting ``footer = True`` to reveal a
    ``&lt;tfoot&gt;`` area that displays simple labels under each column.  This footer can be a useful
    way to then convert the footers to search boxes, as shown in the examples at link just above.

    Column searches are added to the global searches, and follow the same rules for splitting up
    search terms when multiple words are present: words are split on spaces, unless they are quoted
    as a phrase, and once split, the individual terms are all required in order to match a row.
    """

    model = Entry

    class datatable_class(Datatable):
        blog = columns.TextColumn("Blog", sources=["blog__name"])

        class Meta:
            columns = ["headline", "blog"]
            footer = True

    implementation = """dummy"""  # don't hide the block, overridden in template


class SelectRowDatatableView(DemoMixin, DatatableView):
    """
    The official <a href="https://datatables.net/extensions/select/">``Select``
    extension</a> is easy to add to any existing table.  To use it, make sure you include the
    appropriate javascript source file, and add to config following options
    ```{
        style: 'multi',
        selector: 'td:first-child'
    }```
    """

    model = Entry

    class datatable_class(Datatable):
        select_data = columns.CheckBoxSelectColumn()
        blog = columns.TextColumn("Blog", sources=["blog__name"])

        class Meta:
            columns = ["select_data", "headline", "blog"]

    implementation = """dummy"""  # don't hide the block, overridden in template


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
            columns = ["id", "headline", "blog", "pub_date"]
            structure_template = "custom_table_template.html"

    implementation = """
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline', 'blog', 'pub_date']
            structure_template = "custom_table_template.html"

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
            columns = ["id", "headline", "blog", "pub_date"]
            structure_template = ("datatableview/bootstrap_structure.html",)

    implementation = """
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline', 'blog', 'pub_date']
            structure_template = "datatableview/bootstrap_structure.html",

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
            columns = ["id", "headline", "blog", "pub_date"]
            labels = {
                "pub_date": "Publication Date",
            }

    implementation = """
    class MyDatatable(Datatable):
        class Meta:
            columns = ['id', 'headline', 'blog', 'pub_date']
            labels = {
                'pub_date': "Publication Date",
            }

    class CSSStylingDatatableView(DatatableView):
        model = Entry
        datatable_class = MyDatatable
    """
