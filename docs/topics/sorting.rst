Sorting
=======

All sorting takes place on the server.  Your view's :py:attr:`~datatableview.datatables.Datatable` is designed to have all the information it needs to respond to the ajax requests from the client, thanks to each column's :py:attr:`~datatableview.columns.Column.sources` list.  Unlike for searching, the order in which the individual sources are listed might matter to the user.

Important terms concerning column :py:attr:`~datatableview.columns.Column.sources`:

* **db sources**: Sources that are just fields managed by Django, supporting standard queryset lookups.
* **Virtual sources**: Sources that reference not a model field, but an object instance method or property.
* **Compound column**: A Column that declares more than one source.
* **Pure db column, db-backed column**: A Column that defines only db-backed sources.
* **Pure virtual column, virtual column**: A Column that defines only virtual sources.
* **Sourceless column**: A Column that declares no sources at all (likely relying on its processor callback to compute some display value from the model instance).

Pure database columns
---------------------

The ideal scenario for speed and simplicity is that all :py:attr:`~datatableview.columns.Column.sources` are simply queryset lookup paths (to a local model field or to one that is related).  When this is true, the sources list can be sent directly to ``queryset.order_by()``.

Reversing the sort order will reverse all source components, converting a sources list such as ``['id', 'name']`` to ``['-id', '-name']``.  This can be sent directly to ``queryset.order_by()`` as well.

Mixed database and virtual sources
----------------------------------

When a column has more than one source, the ``Datatable`` seeks to determine if there are ANY database sources at all.  If there are, then the virtual ones are discarded for the purposes of sorting, and the strategy for pure database sorting can be followed.

The strategic decision to keep or discard virtual sources is a complex one.  We can't, in fact, just sort by the database fields first, and then blindly do a Python ``sort()`` on the resulting list, because the work performed by ``queryset.order_by()`` would be immediately lost.  Any strategy that involves manually sorting on a virtual column must give up queryset ordering entirely, which makes the rationale for abandoning virtual sources easy to see.

Pure virtual columns
--------------------

When a column provides only virtual sources, the whole queryset will in fact be evaluated as a list and the results sorted in Python accordingly.

Please note that the performance penalty for this is undefined: the larger the queryset (after search filters have been applied), the harder the memory and speed penalty will be.

Columns without sources
-----------------------

When no sources are available, the column automatically become unsortable by default.  This is done to avoid allowing the column to claim the option to sort, yet do nothing when the user clicks on it.
