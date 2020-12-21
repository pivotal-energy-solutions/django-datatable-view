``datatables``
==============

.. py:module:: datatableview.datatables


Server-side Datatables are Form-like classes that are responsible for processing ajax queries from the client.  A Datatable is referenced by a view, and the view initializes the Datatable with the original queryset.  The Datatable is responsible for filtering and sorting the results, and the final object list is handed back to the view for serialization.

A ``Datatable``, like a ``ModelForm``, should contain an inner ``Meta`` class that can declare various options for importing model fields as columns, setting the verbose names, etc.

Datatable
---------


.. autoclass:: Datatable

   :param object_list: The object list that powers the results.
   :type object_list: queryset
   :param str url: The url that will power the ajax responses for this table.  By default, the view
                   arranges to send its own ``request.url``, so that the original view can rebuild
                   the same object and service the request.
   :param view view: The originating class-based view.  This is forwarded as a keyword argument to
                     column processor functions to use if they wish.
   :param object callback_target: An object that will be inspected for
                                  :py:attr:`~datatableview.columns.Column.processor` names that are
                                  not found on the ``Datatable`` directly.  By default this is the
                                  originating class-based view.
   :param Model model: The view's ``model`` or ``queryset.model``.
   :param QueryDict query_config: The ``request.GET`` dictionary that holds options sent by the
                                  client for this particular request.
   :param bool force_distinct: An internal option that can be used to control how ordering on a m2m
                               or reverse fk causes duplicate results to appear in the queryset.
                               All querysets are already made ``.distinct()``, so this option only
                               applies to manually removing result rows with duplicate ``pk`` values
                               when ordering on plural relationships.
   :param dict kwargs: A dict inspected for items named after :py:class:`Meta` options, such as
                       ``'columns'``, which will override settings found in the ``Datatable`` 's own
                       inner ``Meta`` class.  By default, the view that constructs the ``Datatable``
                       will inspect itself for such options as class attributes and send them here
                       as kwargs.

   **Class Attributes**

   .. autoattribute:: options_class

   **Instance Attributes**

   .. attribute:: total_initial_record_count

      The size of the original ``object_list``, used for display purposes for the client.

   .. attribute:: unpaged_record_count

      The size of the result set after search filters have been applied, before paging has been
      applied, used for display purposes for the client.

   **Methods**

   .. automethod:: __str__
   .. automethod:: __iter__
   .. automethod:: resolve_virtual_columns
   .. automethod:: preload_record_data
   .. automethod:: get_extra_record_data

   **Caching Methods**

   .. automethod:: will_load_from_cache
   .. automethod:: get_cache_key_kwargs
   .. automethod:: get_cache_key
   .. automethod:: get_cached_data
   .. automethod:: cache_data
   .. automethod:: get_object_list
   .. automethod:: prepare_object_list_for_cache
   .. automethod:: expand_object_list_from_cache

   **Internal Methods**

   .. automethod:: search
   .. automethod:: sort
   .. automethod:: get_records
   .. automethod:: populate_records
   .. automethod:: get_record_data
   .. automethod:: get_object_pk


ValuesDatatable
---------------

.. autoclass:: ValuesDatatable(**kwargs)
   :members:


Legacy support Datatables
-------------------------



LegacyDatatable
~~~~~~~~~~~~~~~

.. autoclass:: LegacyDatatable(**kwargs)
   :members:

ValuesLegacyDatatable
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: ValuesLegacyDatatable(**kwargs)
   :members:


``Meta`` class and options
--------------------------

.. class:: Meta

   .. attribute:: model

      :Default: ``queryset.model``

      The model class represented by the table.

   .. attribute:: columns

      :Default: All local non-relationship model fields.

      The list of local model fields to be imported from the base model.  The appropriate
      :py:class:`Column` will be generated for each.  Relationship-spanning ORM paths should not be
      used here, nor any "virtual" data getter like a method or property.  For those, you should
      instead declare an explicit column on the :py:class:`Datatable` with a name of your choosing,
      and set the :py:class:`~datatableview.columns.Column.sources` accordingly.

   .. attribute:: exclude

      :Default: ``[]``

      A list of model field names to exclude if ``columns`` is not given.

   .. attribute:: cache_type

      :Default: ``None``

      The identifier for caching strategy to use on the ``object_list`` sent to the datatable.  See
      :doc:`../topics/caching` for more information.

   .. attribute:: ordering

      :Default: The ``model`` 's ``Meta.ordering`` option.

      A list that controls the default table sorting, giving column names in the order of their
      sort priority.  When a Column name is given instead of a model field name, that column's
      :py:class:`~datatableview.columns.Column.sources` list will be looked up for any sortable
      fields it references.

      As with model ordering, using a ``-`` prefix in front of a name will reverse the order.

   .. attribute:: page_length

      :Default: ``25``

      The default page length for response results.  This can be changed by the user, and is
      ultimately in the hands of the client-side JS to configure.

   .. attribute:: search_fields

      :Default: ``[]``

      A list of extra query paths to use when performing searches.  This is useful to reveal results
      that for data points that might not be in the table, but which the user might intuitively
      expect a match.

      :Example: ``['house__city__abbreviation]``

   .. attribute:: unsortable_columns

      :Default: ``[]``

      A list of model fields from ``columns`` that should not be sortable when their
      :py:class:`Column` instances are created.  Explicitly declared columns should send
      ``sortable=False`` instead of listing the column here.

   .. attribute:: hidden_columns

      :Default: ``[]``

      A list of column names that will be transmitted during ajax requests, but which the client
      should hide from the table by default.  Using this setting does not enhance performance.  It
      is purely for datatable export modes to use as a hint.

   .. attribute:: structure_template

      :Default: ``'datatableview/default_structure.html'``

      The template that will be rendered when the :py:class:`Datatable` instance is coerced to a
      string (when the datatable is printed out in a template).  The template serves as the starting
      point for the client-side javascript to initialize.

      The default template creates ``<th>`` headers that have a ``data-name`` attribute that is the
      slug of the column name for easy CSS targeting, and the default search and sort options that
      the ``datatableview.js`` initializer will read to build initialization options.

   .. attribute:: footer

      :Default: ``False``

      Controls the existence of a ``<tfoot>`` element in the table.  If ``True``, the default
      ``structure_template`` will render another set of ``<th>`` elements with appropriate labels.

      This is particularly useful when setting up something like per-column searching, which
      officially leverages the table footer, replacing each simple footer text label with a search
      box that applies only to that column's content.

   .. attribute:: result_counter_id

      :Default: ``'id_count'``

      A helper setting that names a CSS ``id`` that the ``datatableview.js`` initializer will
      configure to hold a total result counter.  This is strictly in addition to the normal readout
      that appears under a datatable.  If you don't want any such external result display, you can
      ignore this setting.

   .. attribute:: labels

      :Default: ``{}``

      A dict of model field names from ``columns`` that should have their ``verbose_name`` setting
      overridden for the table header.

      :Example:
          ``labels = {'name': "Headline"}``

   .. attribute:: processors = None

      :Default: ``{}``

      A dict of model field names from ``columns`` that need to declare a
      :py:attr:`~datatableview.columns.Column.processor` callback.  The mapped values may be
      direct references to callables, or strings that name a method on the Datatable or view.

      :Example:
          ``processors = {'name': 'get_name_data'}``
