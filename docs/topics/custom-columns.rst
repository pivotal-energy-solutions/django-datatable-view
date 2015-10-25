Third-party model fields
========================

Registering fields with custom columns
--------------------------------------

Any model field that subclasses a built-in Django field is automatically supported out of the box, as long as it supports the same query types (``__icontains``, ``__year``, etc) as the original field.

A third-party field that is defined from scratch generally needs to become registered with a :py:class:`~datatableview.columns.Column`.  The most straightforward thing to do is to subclass the base :py:class:`~datatableview.columns.Column`, and set the class attribute :py:attr:`~datatableview.columns.Column.model_field_class` to the third-party field.  This will allow any uses of that model field to automatically select this new column as the handler for its values.

Just by defining the column class, it will be registered as a valid candidate when model fields are automatically paired to column classes.

**Important gotcha**: Make sure the custom class is imported somewhere in the project if you're not already explicitly using it on a table declaration.  If the column is never imported, it won't be registered.

If the column needs to indicate support for new query filter types, declare the class attribute :py:attr:`~datatableview.columns.Column.lookup_types` as a list of those operators (without any leading ``__``).  You should only list query types that make sense when performing a search.  For example, an ``IntegerField`` supports ``__lt``, but using that in searches would be unintuitive and confusing, so it is not included in the default implementation of :py:class:`~datatableview.columns.IntegerColumn`.  You may find that ``exact`` is often the only sensible query type.

New column subclasses are automatically inserted at the top of the priority list when the column system needs to discover a suitable column for a given model field.  This is done to make sure that the system doesn't mistake a third-party field that subclasses a built-in one like ``CharField`` isn't actually mistaken for a simple ``CharField``.

Skipping column registration
----------------------------

Some column subclasses are not suitable for registration.  For example, a custom column that is intended for use on only *some* ``CharField`` fields should definitely not attempt to register itself, since this would imply that all instances of ``CharField`` should use the new column.  An example of this is the built-in :py:class:`~datatableview.columns.DisplayColumn`, which is a convenience class for representing a column that has no sources.

By explicitly setting :py:attr:`~datatableview.columns.Column.model_field_class` to ``None``, the column will be unable to register itself as a handler for any specific model field.  Consequently, it will be up to you to import and use the column where on tables where it makes sense.
