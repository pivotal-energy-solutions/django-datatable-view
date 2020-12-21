#django-datatable-view change log

These logs are also available on GitHub: https://github.com/pivotal-energy-solutions/django-datatable-view/releases

## 0.9.0
This release officially supports Django 1.11, 2.0, and 2.1, and Python 2.7, 3.5, and 3.6.

#### Added TimeColumn
With support of the Django 2-series, we've added a missing TimeColumn to handle the built-in field.  In the future, we intend to look at new ways of handling built-in fields and column registration to minimize such issues.

#### Notes about the future
If you conform to the new Datatable object-style configuration system, having migrated away from legacy ``datatable_options`` dict syntax, you will be able to skip this release and move to 1.0 when it is made available.  0.9 and 1.0 will have parity at release, except that legacy syntaxes will be unrecognized in 1.0.

Please see the 0.9 migration guide provided below if you need help converting to 1.0-style configurations ahead of actually making the jump to 1.0:

https://django-datatable-view.readthedocs.io/en/latest/migration-guide.html

Please note that as of the time of this release, we do not have a live public demo server to interact with.  The example project is included in the release, however, which contains additional short examples and code for the various ways to configure and display a table.  Brief instructions for running that example project are found in the README.

## 0.9.0-beta.6

#### Streamlined ``datatableview.js`` API
We are now using the proper ``DataTable`` "modern" API from datatables.js.

The modern JS API changes the option names and query parameter names.  We've updated those as far as the server-side stuff is concerned, but you should check any options you send to the JS constructors to ensure they match the official, modern datatables API.

The global JS hook ``window.confirm_datatable_options()`` is one step closer to its removal.  ``datatableview.checkGlobalConfirmHook`` will default to true for the time being, which will signal the new hook ``datatableview.finalizeOptions(datatable, options)`` to check for the global hook.  In 1.1, ``checkGlobalConfirmHook`` will default to false, and in 1.2, ``checkGlobalConfirmHook`` will be removed entirely and ``finalizeOptions()`` will be an empty hook for you to do with as you please.

This update aliases names that followed Pythonic naming conventions so that things are more Javascripty:

* ``datatableview.auto_initialize`` to ``datatableview.autoInitialize``
* ``datatableview.make_xeditable`` to ``datatableview.makeXEditable``

The underscore names will be removed in 1.2, simultaneous to the removal of ``datatableview.checkGlobalConfirmHook`` and code for consulting the global hook ``window.confirm_datatable_options()``.

#### QuerySet Caching

An official set of options exists to do automatic queryset caching on a per-View, per-User basis.  For querysets that are a little too heavy for their own good, a caching strategy offers a straightforward optimization.  There's not a good way to fix a bad queryset, but something is better than nothing!

Once configured to use of your Django ``settings.CACHES``, you may opt in a datatable class to use caching via its ``Meta.cache_type`` setting.  Using the default ``cache_types.SIMPLE`` strategy, the queryset is placed directly in your cache for retrieval on subsequent requests.  If that isn't fast enough, you can use ``cache_types.PK_LIST`` instead, which runs your query once to get the pks of the objects and stores that in the cache.  Each request will have to run a ``WHERE `pk` IN (...)`` query but will be signficantly faster than evaluating the original queryset.

1. Set ``settings.DATATABLEVIEW_CACHE_BACKEND`` to an appropriate Django ``CACHES`` name.
2. Opt a python ``Datatable`` subclass into caching by setting ``Datatable.Meta.cache_type`` to one of the cache strategy constants importable at ``datatableview.datatables.cache_types``:
  * ``cache_types.SIMPLE`` (``'simple'``): Stores the view's queryset directly
  * ``cache_types.PK_LIST`` (``'pk_list'``): Stores only the list of pks from the view's queryset.  Each new request will re-query the database with a (hopefully) simpler ``WHERE `pk` IN (...)`` query.
  * ``cache_types.DEFAULT`` (``'default'``): Defers to ``settings.DATATABLEVIEW_DEFAULT_CACHE_TYPE`` for a cache strategy (which is ``SIMPLE`` by default).

Caching for a queryset is unique to the ``kwargs`` that come through the Datatable's ``get_cache_key_kwargs(self, **kwargs)``.  If you need to add or remove items from the dict, modify the dict returned from ``super()`` to suit your needs.

By default, only three items are in the dict:

* ``datatable_class``: The Datatable doing the caching
* ``view``: The view using the Datatable
* ``user``: The view's ``request.user``


## 0.9.0-beta.5
Refinements since 0.9.0-beta.4

* Dropped ``LegacyDatatableView``, renamed ``LegacyConfigurationDatatableView`` to ``LegacyDatatableView`` in its place.
* Added strategy for adding columns that are not registered.  This helps address the issue that columns meant only for some specific interpretations of some columns were being registered for ``CharField``s all over the lonely little planet.
* Added ``CompoundColumn`` to allow explicit use of unregistered column subclasses.
* Add import structure to support accessing the columns from within the ``datatables`` module, hopefully mimicking how ``django.forms`` allows something similar.
* Fixed long-outstanding issue with the column instances declared directly on a datatable being ignored in favor of re-discovering the column class and instantiating it from scratch at runtime.
* Big sphinx documentation updates.
* Removed documentation from live demo site about helpers in favor of linking to the sphinx docs.

## 0.9.0-beta.4
Refinements since 0.9.0-beta.3

Sphinx documentation and Travis CI are now public:

* http://django-datatable-view.readthedocs.org/en/latest/
* https://travis-ci.org/pivotal-energy-solutions/django-datatable-view

Fixes:

* Several issues with LegacyConfiguration innards (sorting, some column names raising unexpected exceptions before the intended exception could be raised)
* Imports for some versions of Django
* Removed forced ``sortable=False`` kwarg when no sources are given (this was causing issues with columns that are expected to be sortable based on processor output)
* Fixed hook lookup for per-column searches
* Changed when internal configuration takes place on a ``Datatable``

## 0.9.0-beta.3
Refinements since 0.9.0-beta.2

We've added Sphinx documentation that we intend to have pushed to readthedocs.org, which will serve as the new primary documentation source.  A new live demo site for 0.9 will be launched soon (we want to keep 0.8 around because of this transitionary period for new syntax), and it will continue to play an important role in providing short and sweet examples, but it's not always a perfect substitute for the actual module documentation.  The documentation is stored at ``django-datatable-view/docs/``, alongside the ``datatableview`` python module.

* Fixed sorting of non-db columns
* Addition of column getter for extra kwargs to be sent to its processor function
* Require column kwarg ``sortable=False`` when no sources are present
* Internal method renames
* ``helpers.through_filter`` renamed to ``helpers.make_processor``

## 0.9.0-beta.2
Refinements since 0.9.0-beta.1

#### New features

It turns out I forgot to reintroduce some old functionality in the new modern column format code, but it's back!

* Support for model fields that use ``choices``.  Specifically, we enable the user to search for the (case-insensitive) label of the various choices and the column will flip the search term to the right thing.  Fixed a bug in 0.8 choices support that made some assumptions that the choice db value was a string (using ``iexact`` too aggressively).
* ``strptime`` date formatting will attempt to parse individual numbers and strings for matches that satisfy format symbols, such as ``%y`` (two digit year) and ``%M`` (month names).

#### Fixes

* Fixed a bug with legacy configuration where a sources list defined as a ``list`` instead of a ``tuple`` would cause dictionary key issues. [43ade82]
* Fixed an issue with ``LegacyConfigurationDatatableView`` skipping the implicit processor discovery phase.  This will be removed in 1.0, but for 0.9 we will continue supporting implicit callbacks when the legacy view is in use. [88a0318]
* Fixed a bug with columns declaring multiple sources that each targeted a value across an m2m relationship, where sources after the first would attempt to inspect the ORM path starting on the model where the first source left off during its own lookup. [4f0af04]
* Fixed an issue with sending multiple column sources directly to the ``link_to_model`` helper, where the generated link text was a ``repr()`` of the source values list, instead of the default ``' '``-joined list of those values. [a27b6eb]
* Changed choices label matching to support partial matches.
* Changed choices label matching to allow multiple matches (since partial matching is now also allowed).  Previously there was a nuance that if two choices had the same label for whatever reason, it was undefined behavior which one would be selected to represent the database value in the converted search query.

## 0.9.0-beta.1
This is a transition release to get people to 1.0, which brings a lot of syntax changes for table declaration on the python view, adopting a strategy that looks a lot like Django's forms framework,
or django-rest-framework's serializers.

0.9 will continue to offer backwards-compatible datatable declaration with the help of a ``LegacyConfigurationDatatableView`` as a baseclass.  ``DatatableView`` will presume that the modern configuration style is being used and will raise errors accordingly.

``wheel`` installation is also possible now.

The live demo site at http://django-datatable-view.appspot.com will continue to operate WITHOUT this beta release, so experimenting with interactive documentation will require that you run the included example project, which includes a 0.9 migration guide.  See the main README.md for quick instructions to get the example project running locally.

## 0.8.2
#### Important future note
This is the last planned release for the 0.8 series!  0.9 and 1.0 will arrive simultaneously sometime during the next couple of weeks, and the entire declaration process for datatableview options has been modernized.

0.9 will include all of the existing "legacy" configuration code from the 0.8 releases, powered by brand new internals.  0.9 will be a no-fuss update, but if you plan to jump up to 1.0, you will need to following the forthcoming migration guide to get away from these "legacy" delcaration syntaxes.

#### Release notes

This release fixes a number of internal issues for newer versions of Django, most notably the tests!   With the introduction of Django's AppConfig system, the hack we've been using (keeping a testing-only app with testing-only models nested inside of the main datatableview app) was broken by a change concerning which app label Django thought the model belonged to.  The tests themselves were doing okay, had they not been failing during the fixture loading process.

@PamelaM has added initial support for including Travis testing into the repository, which is long overdue for a repository that has been gaining popularity over the last couple of years.  I will commit to keeping up with it since, as they sometimes say, an untested app is considered broken by default.

Another Django 1.7 bug with related model fields was fixed, also thanks to @PamelaM.

Other miscellaneous changes:

* The ``datatableview.utils.FIELD_TYPES`` dictionary is now a ``defaultdict(list)`` (@davidfischer-ch)
* PEP-8 spacing changes (@davidfischer-ch)
* Added a ``queryset.distinct()`` to get around some funny ``Q()`` math (@@davidfischer-ch)
* Added/fixed various utf-8 encoding declarations on source files (@davidfischer-ch)
* Preemptive fixes for Django 1.8 and 1.9 import locations (@greenbender)
* Corrected string coercion when ugettext strings were being used as the starting point for looking up a method name (@akx)

## 0.8.1
This release fixes a Django >=1.7 compatibility bug where ORM query lookups would traverse a m2m relationship and incorrectly discover the manager to be a callable value function.

A small translation fix was provided, a wasteful ``count()`` query removed, ``NullBooleanField`` is now added to the 'boolean' FIELD_TYPES, and we fixed a documentation typo that referred users to the wrong javascript callback name.

## 0.8.0
This release modifies the way model fields are detected for ORM queries when submitting a search.  Previously, the approach was primarily hard-coded to support only the core Django fields that served as base classes for all others, but this approach failed to provide any value for third-party fields that were built from scratch.

As of this release, ``datatableview.utils`` contains a dictionary ``FIELD_TYPES`` that contains keys for the major field categories, and maps each one to a list of fields that can be treated identically in ORM query terms.  This dictionary can be extended by importing it and appending new fields to a category.

The default registration dictionary looks like this:

```python
FIELD_TYPES = {
    'text': [models.CharField, models.TextField, models.FileField, models.GenericIPAddressField],
    'date': [models.DateField],
    'boolean': [models.BooleanField],
    'integer': [models.IntegerField, models.AutoField],
    'float': [models.FloatField, models.DecimalField],

    # No direct search ORM queries make sense against these field types
    'ignored': [models.ForeignKey],
}
```

If a field type used in a table but isn't found in any of these categories, the old familiar exception will be raised stating that it is an unhandled field type.  The correct solution is to import this registry and append the field class:

```python
from datatableview.utils import FIELD_TYPES
from netfields.fields import InetAddressField
FIELD_TYPES['text'].append(InetAddressField)
```

In the future, looking towards the full 1.0 release, we would like to offer a more sophistocated field type registration that allows the new field to also declare what unique ORM extensions it offers, in the way that a ``CharField`` offers ``__icontains``, or ``InetAddressField`` offers ``__net_contains``, etc.  Until 1.0, we will be limited to offering this simple registration that limits the field categories to those already listed.

## 0.7.3
This release fixes an exception that is raised when using Django 1.7 release candidate, involving the removal of the deprecated ``StrAndUnicode`` utility base class.

## 0.7.2
This release fixes an issue involving ``verbose_name`` values wrapped in a proxy function used by
Django to defer instantiation of an underlying object.  These proxy values could not go through the ``re`` framework without raising errors about "expecting a string or buffer".

## 0.7.1
This release reverts a change to the Javascript that could cause errors in some cases.  A fix will be reintroduced at a later time to correct a potential issue with Chrome and Safari not updating the footer text when a filter is applied.

The ``default_structure.html`` template has received a minor update to include the use of a CSS class ``"display"`` on the table, which how the datatables.js 1.10.0 version has begun to show examples on their documentation website, which gives the table a more modern default appearance.  The bootstrap template is unchanged.

A fix from @michaeldjeffrey should allow the browser's locale setting to control how the number of results is rendered in the table footer.

A fix from @danmac-uk has been merged that adds Django 1.7 support, because of our current use of Django's ``StrAndUnicode`` base class for the template-renderable datatable object.

Various updates were made to the example project including a fix for "None" table headers in the embedded table demo.

New issues are being tracked at the github repository and we're building our milestone goals for release 1.0.  We would like to include a streamlined strategy for column filters, an updated configuration strategy, and new callbacks to simplify support for datatables new ``"DT_RowData"`` key and modifying the internals of how special field types are handled for ORM querying.

## 0.7.0
This release adds Python 3 support with the help of the [six](http://pythonhosted.org/six/) project.  We've taken some time to verify that unicode handling is handled correctly for both Python 2 and 3 simultaneously.

The options provided by a DatatableView are processed and merged with incoming GET data from ajax calls, and the resulting object replaces the view's ``datatable_options`` attribute at runtime.  Previous to this release, that merged object implemented an attribute API to support lookups like ``options.search`` to get the search string.

As of this release, that attribute API has been removed for the sake of simplicity.  Treat ``options`` like a normal dictionary and use the keys and values it contains to read any options.  The only reason the object is a subclass of the base ``dict`` itself is to provide a constructor that accepts a GET query string and normalizes and validates options.  Other than the normalization phase, it is a dictionary, first and foremost.

## 0.6.5
This release fixes a bug with sorting columns backed by concrete db fields not on the local model.  The sorting operation would fail to recognize the field as concrete and would fall back to text-only sorting, which produced unexpected results.

## 0.6.4
This release adds incremental support for Python 3 (not completed yet, but the occational pull request comes in to help get things ready), and fixes a Python 2.6 compatibility issue with string formatting syntax.

The history of changes on each release has also been added to the code repository, available at ``django-datatable-view/CHANGELOG.md``.

## 0.6.3
This release fixes an issue with non-local fields sometimes raising errors when requested for sorting operations over ajax.

## 0.6.2
This release fixes a mistake that was made because the author was overconfident about the jQuery-dataTables API interchangeability.

The return value of the Javascript late initialization function ``datatableview.initialize()`` should now work like this:

```javascript
$(function(){
    var oTable = datatableview.initialize($(".datatable"));
});
```

Release 0.6.1 mistakenly returned an awkward set of nested arrays, leading to a need to re-call the ``dataTable()`` constructor, defeating the purpose of the return value as a convenience.

## 0.6.1
This release adds a return statement to the ``datatableview.initialize()`` javascript function that was added in version 0.6.0.  The returned value is the jQuery collection of objects that are the initialized ``oTable`` objects from the initialization process.  This should support multiple or single initializations with a uniform interaction.

## 0.6.0
This release makes a number of changes for the benefit of flexibility and future development.

#### utils.get_datatable_structure() and DatatableStructure

Unfortunately, I made a decision to reverse the 2nd and 3rd arguments of this utility function.  The only reason the model class was being sent to the utility at all was because of certain default conditions that, if options weren't specified (like a column list, or the preferred ordering), the internals could look up those details and fill them in.

The reality was that supplying the model here was 9 times out of 10 not required.  The argument has been moved to the end of the parameter list, and now accepts ``None`` as a default value, making the signature:

```python
get_datatable_structure(ajax_url, options, model=None)
```

The constructor to the internal context variable object ``DatatableStructure`` matches this signature.

#### Helpers

* ``format_date``: This helper used to have trouble with columns that were ``null=True``, and would likely raise an error, worse even when the ``localize=True`` argument was set.  The helper now aborts sooner in its rendering process if the value is ``None``, returning the blank string.
* ``through_filter``: A new helper that takes a simple callable mapping function (e.g., takes one argument, returns a new value), wrapping that target function so that it is compatible with use as a column callback.  Django template filters are good examples of target functions.  These can not be used directly as callbacks because they don't accept extra ``**kwargs`` that get sent by the caller.  This helper swallows those extra arguments so that the target function can do its work.
* ``itemgetter`` and ``attrgetter``: While still convenient shorthand, these aren't strictly necessary anymore.  ``through_filter`` can wrap the built-in ``operator.itemgetter`` and ``operator.attrgetter`` and accomplish the same thing.  ``itemgetter`` still supports an ``ellipsis="..."`` argument, but more robust behavior can probably be found using ``through_filter(django.template.defaultfilters.truncatechars)``.

#### datatableview.js

Automatic initialization of tables via a jQuery ``document.ready`` event is still enabled by default, but it can be turned off via a global object property.  If the following is executed after you include the ``datatableview.js`` file, but before the jQuery ready handler, no tables will be initialized:

```javascript
datatableview.auto_initialize = false;
```

In this scenario, you can do late initialization and option declaration on your own, using the same global object:

```javascript
var datatableOptions = {};
datatableview.initialize($(".mytable"), datatableOptions);
```

Note that all of the configuration options specified on the view are represented on the DOM in ``data-*`` attributes.  dataTables.js doesn't actually support these, but this ``datatableview.initialize`` function does.  This method of late binding can also replace the need to use the global javascript hook ``confirm_datatable_options`` to specify options for tables that were previously being auto-initialized.

#### Bootstrap integration

To make your life slightly easier, we've included a new template fragment at ``datatableview/bootstrap_structure.html``.  This inclusion template simply adds the Bootstrap-esque ``table striped-table bordered-table`` classes to the main ``<table>`` tag.

To use this template, you can either specify on your view's options ``datatable_options["structure_template"] = "datatableview/bootstrap_structure.html"``, or you can copy the contents of this file into your own overridden ``"datatableview/default_structure.html"`` as a starting point for customization.

#### Tests

This release adds a set of tests for the ``helpers`` and ``utils`` modules, and for the new example project's views.

#### Example project

http://django-datatable-view.appspot.com/ — This is a public instance of the new example project, which includes live demos, descriptions, and short code examples.

The goal of this example project is to replace the incredibly long-winded README that was previously the only real information resource.  While a Django-powered example project might feel more annoying to set up, it's the only way to provide actual live demos, instead of faking them and defeating the purpose of the exercise.

The new example project is included as part of the ``datatableview.tests`` module.  The easiest way to get it running on your own machine is to do something like this:

```bash
$ git clone https://github.com/pivotal-energy-solutions/django-datatable-view.git
$ cd django-datatable-view
$ mkvirtualenv datatableview
(datatableview)$ pip install -r requirements.txt
(datatableview)$ datatableview/tests/example_project/manage.py syncdb
(datatableview)$ datatableview/tests/example_project/manage.py runserver
```

This downloads the latest code, uses virtualenvwrapper to set up a new environment, and installs the basic requirements for the project (Django and python-dateutil).  After that, it's just a matter of sync-ing the sqlite3 database and running the dev server.

## Smaller things

Less important for the average use cases, but maybe good to know:

* Detection of the default column value sent to a helper has been improved.  If values were ``False``-like, they were sometimes ignored as not being present, which led to the helper trying to act upon the row's instance as a fallback value.  This usually didn't produce an intuitive result.
* Due to the above point, the ``key`` argument to a few of the helpers is facing removal sometime in the future.
* Minor parameter-passing bug with the new ``make_xeditable`` helper.
* Added a utility that normalizes field definitions to an internal format.  Unless there was a lot of modification of the ``DatatableView``'s internal methods for deriving column data, this change shouldn't have an outward impact.
* Fixed bug concerning default "show all columns" mode and no data appearing in the rows
* Fixed bug that prevented the same field from being represented in multiple columns.  The field was reduced to a dictionary mapping to column definitions, which resulted in dropping one at random.  All column definitions are now properly respected.
* Fixed bug with Django < 1.5 versions using the ``XEditableDatatableView``.  The asynchronous ajax updates failed due to the use of a Django 1.5 ``update_fields`` parameter to the ``save()`` method.  Django 1.5 will still attempt to use this option, but older versions will not.
* Fixed bug with status code in ``make_xeditable`` responses.

## 0.5.5
This release fixes a mistake in the ``format_date`` helper function that prevented it from returning the expected output in a non-``key`` usage.

Thanks to @foobar76 for raising the issue.

## 0.5.4
Addresses the following issues:

* #19 — Uses py3 ``collections.UserDict`` if possible
* #20 — Defer object_list pagination until serialization time, not in ``apply_queryset_options()``.
* #16 — Built-in support for [x-editable](http://vitalets.github.io/x-editable/) datatables.  See documentation for a new view base class [``XEditableDatatableView``](https://github.com/pivotal-energy-solutions/django-datatable-view#x-editable-datatables) and the new [``make_xeditable()``](https://github.com/pivotal-energy-solutions/django-datatable-view#make_xeditable) helper for details on how to get this working with minimal configuration.

A backwards-incompatible change has been made to the return value of ``get_object_list()`` and ``apply_queryset_options()``, and the parameter type of ``serialize_to_json()``.  The former two methods previously returned a 3-tuple of ``(object_list, total, filtered_total)``, and the latter method received this 3-tuple as a single argument.  This was not ideal, so the former two are now updated to return a list-like object, and the latter method now receives just the python dictionary to serialize.

A new method has been broken out of the ``DatatableView`` request-response workflow:

[get_json_response_object()](https://github.com/pivotal-energy-solutions/django-datatable-view#get_json_response_objectobject_list-total-filtered_total) — This method receives several arguments that will be placed into a dictionary.  If custom fields need to be added to the AJAX response object, you can implement this method, call ``super()`` to get the normal object, and then add to it:

```python
class MyDatatableView(DatatableView):
    datatable_options = { ... }
    def get_json_response_object(self, object_list, *args, **kwargs):
        data = super(MyDatatableView, self).get_json_response_object(object_list, *args, **kwargs)

        # Keep customizations JSON-compatible! :)
        data.update({
            'special_arg': self.kwargs['special_arg'],
        })
        return data
```

## 0.5.1
Addressed in this bugfix release:

* #17 'console' is undefined error in IE8
* #8 pypi integration? — packaging error excluded relevant package_data items from being included in an sdist release

## 0.5.0
This is the first PyPI-compatible release.
