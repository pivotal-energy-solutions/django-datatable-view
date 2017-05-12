``columns``
===========

.. py:module:: datatableview.columns


Column
------

.. autoclass:: Column

   Subclasses of :py:class:`Column` automatically register themselves as handlers of certain
   model fields, using :py:attr:`.model_field_class` and :py:attr:`.handles_field_classes` to offer
   support for whichever ``ModelField`` types they wish.

   External subclasses will automatically override those found in this module.

   Custom columns are not necessarily required when a third-party ``ModelField`` subclasses a
   built-in one, like ``CharField``.  If the field however offers special query lookups, a dedicated
   column can be declared and the query lookups specified by its :py:attr:`lookup_types` list.

   :param str label: The verbose name shown on the table header.  If omitted, the first item in
                     ``sources`` is checked for a ``verbose_name`` of its own.
   :param list sources: A list of strings that define which fields on an object instance will be
                        supply the value for this column.  Model field names (including query
                        language syntax) and model attribute, method, and property names are all
                        valid source names.  All sources in the list should share a common model
                        field class.  If they do not, see :py:class:`CompoundColumn` for information
                        on separating the sources by type.
   :param str source: A convenience parameter for specifying just one source name.  Cannot be used
                      at the same time as ``sources``.
   :param processor: A reference to a callback that can modify the column source data before
                     serialization and transmission to the client.  Direct callable references will
                     be used as-is, but strings will be used to look up that callable as a method of
                     the column's :py:class:`~datatableview.datatables.Datatable` (or failing that,
                     the view that is serving the table).
   :type processor: callable or str
   :param str separator: The string that joins multiple source values together if more than one
                         source is declared. This is primarily a zero-configuration courtesy, and
                         in most situations the developer should provide a :py:attr:`processor`
                         callback that does the right thing with compound columns.
   :param str empty_value: The string shown as the column value when the column's source(s) are
                           ``None``.
   :param bool sortable: Controls whether the rendered table will allow user sorting.
   :param bool visible: Controls whether the ``bVisible`` flag is set for the frontend.  A
                        ``visible=False`` column is still generated and transmitted over ajax
                        requests for the table.
   :param bool localize: A special hint sent to processor callbacks to use.
   :param bool allow_regex: Adds ``__iregex`` as a query lookup type for this instance of the
                            column.
   :param bool allow_full_text_search: Adds ``__search`` as a query lookup type for this instance of
                                       the column.  Make sure your database backend and column type
                                       support this query type before enabling it.

   **Class Attributes**

   .. autoattribute:: model_field_class

      References the core ``ModelField`` type that can represent this column's data in the backend.

   .. autoattribute:: handles_field_classes

      References to additional ``ModelField`` types that can be supported by this column.

   .. autoattribute:: lookup_types

      ORM query types supported by the underlying :py:attr:`model_field_class`.  The default types
      show bias for text-type fields in order for custom fields that don't subclass Django's
      ``CharField`` to be handled automatically.

      Subclasses should provide query lookups that make sense in the context of searching.  If
      required, input coercion (from a string to some other type) should be handled in
      :py:meth:`.prep_search_value`, where you have the option to reject invalid search terms for a
      given lookup type.

   **Instance Attributes**

   .. attribute:: sources

      A list of strings that define which fields on an object instance will be supply the value for
      this column.  Model field names and extra :py:class:`Datatable` column declarations are valid
      source names.

   .. attribute:: processor

      A reference to a callback that can modify the column source data before serialization and
      transmission to the client. Direct callable references will be used as-is, but strings will
      be used to look up that callable as a method of the column's :py:class:`Datatable` (or
      failing that, the view that is serving the table).

   **Properties**

   .. autoattribute:: attributes

   **Methods**

   .. automethod:: __str__

       Renders a simple ``<th>`` element with ``data-name`` attribute.  All items found in the
       ``self.attributes`` dict are also added as attributes.

   .. automethod:: search
   .. automethod:: prep_search_value
   .. automethod:: value
   .. automethod:: get_initial_value
   .. automethod:: get_source_value
   .. automethod:: get_processor_kwargs

   **Internal Methods**

   .. automethod:: get_db_sources
   .. automethod:: get_virtual_sources
   .. automethod:: get_sort_fields
   .. automethod:: get_lookup_types


Available Columns
-----------------

Model fields that subclass model fields shown here are automatically covered by these columns, which
is why not all built-in model fields require their own column class, or are even listed in the
handled classes.


TextColumn
~~~~~~~~~~

.. autoclass:: TextColumn(**kwargs)

   .. autoattribute:: model_field_class
      :annotation: = CharField
   .. autoattribute:: handles_field_classes
      :annotation: = [CharField, TextField, FileField]
   .. autoattribute:: lookup_types

IntegerColumn
~~~~~~~~~~~~~

.. autoclass:: IntegerColumn(**kwargs)

   .. autoattribute:: model_field_class
      :annotation: = IntegerField
   .. autoattribute:: handles_field_classes
      :annotation: = [IntegerField, AutoField]
   .. autoattribute:: lookup_types

FloatColumn
~~~~~~~~~~~

.. autoclass:: FloatColumn(**kwargs)

   .. autoattribute:: model_field_class
      :annotation: = FloatField
   .. autoattribute:: handles_field_classes
      :annotation: = [FloatField, DecimalField]
   .. autoattribute:: lookup_types

DateColumn
~~~~~~~~~~

.. autoclass:: DateColumn(**kwargs)

   .. autoattribute:: model_field_class
      :annotation: = DateField
   .. autoattribute:: handles_field_classes
      :annotation: = [DateField]
   .. autoattribute:: lookup_types

DateTimeColumn
~~~~~~~~~~~~~~

.. autoclass:: DateTimeColumn(**kwargs)

   .. autoattribute:: model_field_class
      :annotation: = DateTimeField
   .. autoattribute:: handles_field_classes
      :annotation: = [DateTimeField]
   .. autoattribute:: lookup_types

BooleanColumn
~~~~~~~~~~~~~

.. autoclass:: BooleanColumn(**kwargs)

   .. autoattribute:: model_field_class
      :annotation: = BooleanField
   .. autoattribute:: handles_field_classes
      :annotation: = [BooleanField, NullBooleanField]
   .. autoattribute:: lookup_types

DisplayColumn
~~~~~~~~~~~~~

.. autoclass:: DisplayColumn(**kwargs)

   .. autoattribute:: model_field_class
      :annotation: = None
   .. autoattribute:: handles_field_classes
      :annotation: = []
   .. autoattribute:: lookup_types

CompoundColumn
~~~~~~~~~~~~~~

.. autoclass:: CompoundColumn(**kwargs)

   .. autoattribute:: model_field_class
      :annotation: = None
   .. autoattribute:: handles_field_classes
      :annotation: = []
   .. autoattribute:: lookup_types
