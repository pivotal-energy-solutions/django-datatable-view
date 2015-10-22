``helpers``
===========
.. py:module:: datatableview.helpers


The ``helpers`` module contains functions that can be supplied directly as a column's :py:attr:`~datatableview.columns.Column.processor`.

Callbacks need to accept the object instance, and arbitrary other ``**kwargs``, because the ``Datatable`` instance will send it contextual information about the column being processed, such as the default value the column contains, the originating view, and any custom keyword arguments supplied by you from :py:meth:`~datatableview.datatables.Datatable.preload_record_data`.

link_to_model
-------------

.. autofunction:: link_to_model(instance, text=None, **kwargs)

make_boolean_checkmark
----------------------

.. autofunction:: make_boolean_checkmark(value, true_value="✔", false_value="✘", *args, **kwargs)

itemgetter
----------

.. autofunction:: itemgetter

attrgetter
----------

.. autofunction:: attrgetter

format_date
-----------

.. autofunction:: format_date

format
------

.. autofunction:: format(format_string, cast=<identity function>)

make_xeditable
--------------

.. autofunction:: make_xeditable

make_processor
--------------

.. autofunction:: make_processor
