``forms``
=========
.. py:module:: datatableview.forms


XEditableUpdateForm
-------------------

The X-Editable mechanism works by sending events to the view that indicate the user's desire to
open a field for editing, and their intent to save a new value to the active record.

The ajax ``request.POST['name']`` data field name that tells us which of the model
fields should be targetted by this form.  An appropriate formfield is looked up for that model
field, and the ``request.POST['value']`` data will be inserted as the field's value.

.. autoclass:: XEditableUpdateForm

   :param Model model: The model class represented in the datatable.

   .. automethod:: set_value_field
   .. automethod:: clean_name
