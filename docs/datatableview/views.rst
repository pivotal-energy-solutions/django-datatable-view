``views``
=========

DatatableView
-------------

.. py:module:: datatableview.views.base


.. autoclass:: DatatableMixin
   :members:

.. autoclass:: DatatableView


``views.xeditable``
-------------------
.. py:module:: datatableview.views.xeditable


.. autoclass:: XEditableMixin
   :members:

.. autoclass:: XEditableDatatableView


``views.legacy``
----------------
.. py:module:: datatableview.views.legacy


The ``legacy`` module holds most of the support utilities required to make the old tuple-based configuration syntax work.

There are two different ways to get legacy support.

Preferred legacy mode
~~~~~~~~~~~~~~~~~~~~~

The preferred legacy mechanism is to use :py:class:`LegacyConfigurationDatatableView` as your view's base class instead of :py:class:`DatatableView`, and then declare a class attribute ``datatable_options`` as usual.  This strategy simply translates the old syntax to the new syntax.  Certain legacy internal hooks and methods will no longer be available.

.. autoclass:: LegacyConfigurationDatatableMixin

   .. autoattribute:: datatable_options
      :annotation: = {}

   .. autoattribute:: datatable_class
      :annotation: = LegacyDatatable
      
      The :py:class:`~datatableview.datatables.LegacyDatatable` will help convert the more
      extravagant legacy tuple syntaxes into full :py:class:`~datatableview.columns.Column`
      instances.

.. autoclass:: LegacyConfigurationDatatableView

"Things are going horribly wrong and I don't know why" legacy mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The other way to get legacy support is to use :py:class:`LegacyDatatableView` to switch to pure legacy utilities and internal methods.  Some behaviors of ``django-datatable-view`` documented here may not be consistent with how legacy mode works, specifically when trying to handle custom model fields.  This strategy should be avoided.  Support for it will be removed in version 1.0.

.. autoclass:: LegacyDatatableMixin

   .. automethod:: get
   .. automethod:: get_ajax
   .. automethod:: get_object_list
   .. automethod:: get_datatable_options
   .. automethod:: _get_datatable_options
   .. automethod:: apply_queryset_options
   .. automethod:: get_datatable_context_name
   .. automethod:: get_datatable
   .. automethod:: get_context_data
   .. automethod:: get_json_response_object
   .. automethod:: paginate_object_list
   .. automethod:: serialize_to_json
   .. automethod:: get_record_data
   .. automethod:: get_column_data
   .. automethod:: preload_record_data
   .. automethod:: _get_preloaded_data
   .. automethod:: _get_resolver_method
   .. automethod:: _get_column_data_default

.. autoclass:: LegacyDatatableView
