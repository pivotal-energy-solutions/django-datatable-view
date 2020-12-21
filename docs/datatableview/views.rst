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

Use :py:class:`LegacyDatatableView` as your view's base class instead of :py:class:`DatatableView`, and then declare a class attribute ``datatable_options`` as usual.  This strategy simply translates the old syntax to the new syntax.  Certain legacy internal hooks and methods will no longer be available.

.. autoclass:: LegacyDatatableMixin

   .. autoattribute:: datatable_options
      :annotation: = {}

   .. autoattribute:: datatable_class
      :annotation: = LegacyDatatable

      The :py:class:`~datatableview.datatables.LegacyDatatable` will help convert the more
      extravagant legacy tuple syntaxes into full :py:class:`~datatableview.columns.Column`
      instances.

.. autoclass:: LegacyDatatableView
