Searching
=========

All searching takes place on the server.  Your view's :py:attr:`~datatableview.datatables.Datatable` is designed to have all the information it needs to respond to the ajax requests from the client, thanks to each column's :py:attr:`~datatableview.columns.Column.sources` list.  The order in which the individual sources are listed does not matter (although it does matter for :doc:`sorting`).

Sources that refer to non-``ModelField`` attributes (such as methods and properties of the object) are not included in searches.  Manual searches would mean fetching the full, unfiltered queryset on every single ajax request, just to be sure that no results were excluded before a call to ``queryset.filter()``.

Important terms concerning column :py:attr:`~datatableview.columns.Column.sources`:

* **db sources**: Sources that are just fields managed by Django, supporting standard queryset lookups.
* **Virtual sources**: Sources that reference not a model field, but an object instance method or property.
* **Compound column**: A Column that declares more than one source.
* **Pure db column, db-backed column**: A Column that defines only db-backed sources.
* **Pure virtual column, virtual column**: A Column that defines only virtual sources.
* **Sourceless column**: A Column that declares no sources at all (likely relying on its processor callback to compute some display value from the model instance).

Parsing the search string
-------------------------

When given a search string, the :py:attr:`~datatableview.datatables.Datatable` splits up the string on spaces (except for quoted strings, which are protected).  Each "term" is required to be satisfied somewhere in the object's collection of column :py:attr:`~datatableview.columns.Column.sources`.

For each term, the table's :py:attr:`~datatableview.columns.Column` objects are asked to each provide a filter ``Q()`` object for that term.

Deriving the ``Q()`` filter
---------------------------

Terms are just free-form strings from the user, and may not be suitable for the column's data type.  For example, the user could search for ``"54C-NN"``, and a integer-based column simply cannot coerce that term to something usable.  Similar, searching for ``"13"`` is an integer, but isn't suitable for a ``DateTimeField`` to query as a ``__month``.

Consequently, a column has the right to reject any search term that it is asked to build a query for.  This allows columns to protect themselves from building invalid queries, and gives the developer a way to modify their own columns to decide what terms mean in the context of the data type they hold.

A column's :py:meth:`~datatableview.columns.Column.search` method is called once per term.  The default implementation narrows its :py:attr:`~datatableview.columns.Column.sources` down to just those that represent model fields, and then builds a query for each source, combining them with an ``OR`` operator.  All of the different column ``Q()`` objects are then also combined with the ``OR`` operator, because global search terms can appear in any column.

The only place an ``AND`` operator is used is from within the :py:attr:`~datatableview.datatables.Datatable`, which is combining all the results from the individual per-column term queries to make sure all terms are found.

Compound columns with different data types
------------------------------------------

Multiple sources in a single column don't need to be the same data type.  This is a quirk of the column system.  Each source is automatically matched to one of the provided :py:class:`~datatableview.columns.Column` classes, looked up based on the source's model field class.  This allows the column to ask internal copies of those column classes for query information, respecting the differences between data types and coercion requirements.
