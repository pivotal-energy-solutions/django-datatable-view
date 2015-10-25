The client and server interaction model
=======================================

High-level description
----------------------

Traditionally, developers using ``dataTables.js`` have approached their table designs from the client side.  An ajax backend is just an implementation detail that can be enabled "if you need one."

From the perspective of a Django application, however, we want to flip things around: the ``datatableview`` module has all of the tools required to build a server-side representation of your table, such as the column names, how it derives the information each column holds, and which sorting and filtering features it will expose.

The execution steps for a server-driven table look like this:

* The developer declares a view.
* The view holds a table configuration object (like a Django ``ModelForm``).
* The view puts the table object in the template rendering context.
* The template renders the table object directly into the HTML, which includes its own template fragment to put the basic table structure on the page.  (We happen to render a few ``data-*`` attributes on the ``<th>`` headers in the default template, but otherwise, the template isn't very interesting.)
* The developer uses a javascript one-liner to initialize the table to get ``dataTables.js`` involved.

From then on, the process is a loop of the user asking for changes to the table, and the server responding with the new data set:

* The client sends an ajax request with ``GET`` parameters to the current page url.
* The view uses the same table configuration object as before.
* The view gives the table object the initial queryset.
* The table configuration object overrides its default settings with any applicable ``GET`` parameters (sorting, searches, current page number, etc).
* The table configuration object applies changes to the queryset.
* The view serializes the final result set and responds to the client.

Expanded details about some of these phases are found below.

The table configuration object
------------------------------

The :py:class:`~datatableview.datatables.Datatable` configuration object encapsulates everything that the server understands about the table.  It knows how to render its initial skeleton as HTML, and it knows what to do with a queryset based on incoming ``GET`` parameter data from the client.  It is designed to resemble the Django ``ModelForm``.

The resemblance with ``ModelForm`` includes the use of an inner :py:class:`~datatableview.datatables.Meta` class, which can specify which model class the table is working with, which fields from that model to import, which column is sorted by default, which template is used to render the table's HTML skeleton, etc.

:py:class:`~datatableview.columns.Column` s can be added to the table that aren't just simple model fields, however.  Columns can declare any number of :py:attr:`~datatableview.columns.Column.sources`, including the output of instance methods and properties, all of which can then be formatted to a desired HTML result.  Columns need not correspond to just a single model field!

The column is responsible for revealing the data about an object (based on the ``sources`` it was given), and then formatting that data as a suitable final result (including HTML).

Update the configuration from ``GET`` parameters
------------------------------------------------

Many of the options declared on a :py:class:`~datatableview.datatables.Datatable` are considered protected.  The column definitions themselves, for example, cannot be changed by a client playing with ``GET`` data.  Similarly, the table knows which columns it holds, and it will not allow filters or sorting on data that it hasn't been instructed to inspect.  ``GET`` parameters are normalized and ultimately thrown out if they don't agree with what the server-side table knows about the table.

Generating the queryset filter
------------------------------

Because each column in the table has its :py:attr:`~datatableview.columns.Column.sources` plainly declared by the developer, the table gathers all of the sources that represent model fields (even across relationships).  For each such source, the table matches it to a core column type and uses that as an interface to ask for a ``Q()`` filter for a given search term.

The table combines all of the discovered filters together, making a single ``Q()`` object, and then filters the queryset in a single step.

Read :doc:`searching` for more information about how a column builds its ``Q()`` object.

The client table HTML and javascript of course don't know anything about the server's notion of column sources, even when using column-specific filter widgets.

Sorting the table by column
---------------------------

Because a column is allowed to refer to more than one supporting data source, "sorting by a column" actually means that the list of sources is considered as a whole.

Read :doc:`sorting` to understand the different ways sorting can be handled based on the composition of the column's sources.

As with searching, the client table HTML and javascript have no visibility into the column's underlying sources.  It simply asks for a certain column index to be sorted, and the server's table representation decides what that means.
