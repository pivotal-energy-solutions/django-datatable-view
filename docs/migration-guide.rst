0.9 Migration Guide
===================

The jump from the 0.8.x series to 0.9 is covered in sections below.

dataTables.js 1.10
------------------

:Note: See `the official 1.10 announcement`__ if you've been living under a rock!

__ http://datatables.net/blog/2014-05-01

DataTables 1.10 provides a brand new api for getting things done, and it's a good thing too, because doing anything fancy in the old api pretty much required Allan to write yet another block of example code that everyone just copies and pastes.

For our 0.9 release of django-datatable-view, we still use the "legacy" constructor to get things going, but that's okay, because the legacy api is still completely supported (even if all of its Hungarian notation keeps us up at night). The drawback at this stage is that we can't yet accept configuration settings that are "new-style only".

Despite the fact that we're using the legacy constructor for a while longer, you can access the table's fancy new API object with one simple line::

    // Standard initialization
    var opts = {};
    var datatable = datatableview.initialize($('.datatable'), opts);

    // Get a reference to the new API object
    var table = datatable.api();

Update configuration style
--------------------------

:Note: See `Datatable object and Meta`__ for examples.

__ {% url "configure-datatable-object" %}

The preferred way to configure columns for a view is now to use the :py:class:`~datatableview.datatables.Datatable` class. It has similarities to the Django ``ModelForm``: the class uses an inner :py:class:`~datatableview.datatables.Meta` class to specify all of the options that we used to provide in your view's ``datatable_options`` dict.

You want to just unpack the keys and values from your existing ``datatable_options`` dict and set those as attributes on a :py:class:`~datatableview.datatables.Meta`. Then just assign this :py:class:`~datatableview.datatables.Datatable` subclass on your view::

    class MyDatatable(Datatable):
        class Meta:
            columns = [ ... ]
            search_fields = [ ... ]
            # etc

    class MyDatatableView(DatatableView):
        datatable_class = MyDatatable

An alternate abbreviated style is available: as with class-based views that use Django forms, you can set these ``Meta`` attributes directly on the view class, `shown in more detail here`__.  Please note that if you're declaring anything fancier than simple model fields or methods as columns (typically anything that would have required the 2-tuple or 3-tuple column syntax), please use the new ``Datatable`` object strategy.

__ {% url "configure-inline" %}

The new ``Datatable`` object doubles as the old 0.8 ``DatatableOptions`` template renderable object.  ``DatatableOptions`` and ``utils.get_datatable_structure()`` have both been removed, since ``Datatable`` itself is all you need.


New vocabulary
--------------

:Celebrate: We're becoming more sophisticated!

Now that we spent a bunch of time learning how to use the tools we created, it felt like a good
time to change some of the terms used internally.

In connection with the new ``Datatable`` object that helps you design the datatable, **we've started referring to column data callbacks as "processors"**. This means that we will stop relying on callbacks in the documentation being named in the pattern of ``'get_column_FOO_data()'``. Instead, you'll notice names like ``'get_FOO_data()'``, and we'll be specifying the callback in a column definition via a ``processor`` keyword argument. See `Postprocessors`__ for a examples of this.

__ {% url "processors" %}


No more automatic column callbacks
----------------------------------

    :The Zen of Python: Explicit is better than implicit.

We knew that implicit callbacks was a bad idea, but in our defense, `the deprecated column format was really cumbersome to use`__, and implicit callbacks were saving us some keystrokes.  **This behavior is going away in version 1.0.**  We continue to support implicit callbacks so that 0.9 is a backwards-compatible release with 0.8.  If you have any column callbacks (we're calling them "processors" now) that aren't explicitly named in the column definition, please update your code soon!

__ {% url "column-formats" %}


No more automatic dataTables.js initialization
----------------------------------------------

:Note: Bye bye ``function confirm_datatable_options(options){ ... }``

Automatic initialization has gone the way of the buffalo, meaning that it doesn't exist anymore.  The global JavaScript function ``confirm_datatable_options`` only ever existed because auto initialization took away your chance to set custom options during the init process.  You should initialize your datatables via a simple call to the global function ``datatableview.initialize($('.datatable'), opts)``.  This JS function reads DOM attributes from the table structure and builds some of the column options for you, but you can pass literally any other supported option in as the second argument. Just give it an object, and everything will be normal.

There is a configurable Javascript flag ``datatableview.auto_initialize`` that
previously defaulted to ``true``, but in 0.9 its default value is now
``false``.  If you need 0.9 to behave the way it did in 0.8, set this flag globally
or per-page as needed.  (Be careful not to do it in a ``$(document).ready()``
handler, since auto initialization runs during that hook.  You might end up flagging for
auto initialization after datatableview.js has already finished checking it, and nothing
will happen.)


Double check your default structure template
--------------------------------------------

:Note: See `Custom render template`__ for examples.

__ {% url "customized-template" %}

If you haven't gone out of your way to override the default structure template or create your own template, this shouldn't apply to you.

The 0.9 default structure template at ``datatableview/default_structure.html`` has been modified to include a reference to a ``{% templatetag openvariable %} config {% templatetag closevariable %}`` variable, which holds all of the configuration values for the table.  The render context for this template previously held a few select loose values for putting ``data-*`` attributes on the main ``<table>`` tag, but the template should now read from the following values (note the leading ``config.``:

    * ``{{ config.result_counter_id }}``
    * ``{{ config.page_length }}``


Update complex column definitions
---------------------------------

:Note: See `Custom verbose names`__, `Model method-backed columns`__, `Postprocessing values`__, and `Compound columns`__ for examples.

__ /pretty-names/
__ /column-backed-by-method/
__ /processors/
__ /compound-columns/

The `now-deprecated 0.8 column definition format`__ had a lot of overloaded syntax.  It grew out of a desire for a simple zero-configuration example, but became unwieldy, using nested tuples and optional tuple lengths to mean different things.

__ /column-formats/

The new format can be thought of as a clone of the built-in Django forms framework.  In that comparison, the new ``Datatable`` class is like a Form, complete with Meta options that describe its features, and it defines ``Column`` objects instead of FormFields.  A ``Datatable`` configuration object is then given to the view in the place of the old ``datatable_options`` dictionary.

In summary, the old ``datatable_options`` dict is replaced by making a ``Datatable`` configuration object that has a ``Meta``.

The task of `showing just a few specific columns`__ is made a bit heavier than before, but (as with the forms framework) the new Meta options can all be provided as class attributes on the view to keep the simplest cases simple.

__ /specific-columns/


Custom model fields
-------------------

:Note: See `Custom model fields`__ for new registration strategy.

__ /custom-model-fields/

Custom model fields were previously registered in a dict in ``datatableview.utils.FIELD_TYPES``, where the type (such as ``'text'``) would map to a list of model fields that conformed to the text-style ORM query types (such as ``__icontains``).

In 0.9, the registration mechanism has changed to a priority system list, which associates instances of the new ``Column`` class to the model fields it can handle.  See `Custom model fields`__ for examples showing how to register model fields to a built-in ``Column`` class, and how to write a new ``Column`` subclass if there are custom ORM query types that the field should support.

__ /custom-model-fields/


Experiment with the new ``ValuesDatatable``
-------------------------------------------

:Note: See `ValuesDatatable object`__ for examples.

__ {% url "configure-values-datatable-object" %}

An elegant simplification of the datatable strategy is to select the values you want to show directly from the database and just put them through to the frontend with little or no processing.  If you can give up declaration of column sources as model methods and properties, and rely just on the data itself to be usable, try swapping in a ``ValuesDatatable`` as the base class for your table, rather than the default ``Datatable``.

This saves Django the trouble of instantiating model instances for each row, and might even encourage the developer to think about their data with fewer layers of abstraction.
