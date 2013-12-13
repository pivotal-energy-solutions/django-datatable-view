# Datatable View

This package is used in conjunction with the jQuery plugin [DataTables](http://datatables.net/), and supports state-saving detection with [fnSetFilteringDelay](http://datatables.net/plug-ins/api).  The package consists of a class-based view, and a small collection of utilities for rendering table data from models.

Dependencies:

* [dateutil](http://labix.org/python-dateutil) library for flexible, fault-tolerant date parsing.
* [Django](http://www.djangoproject.com/) >= 1.2

# Features at a glance

* ``DatatableView``, a drop-in replacement for ``ListView`` that allows options to be specified for the datatable that will be rendered on the page.
* Verbose names as column headers
* Customizable table headers
* Compound columns (columns representing more than one model field)
* Columns backed by methods or callbacks instead of model fields
* Easy related fields
* Automatic searching support
* Ajax paging
* Zero queries on initial page load (no queryset evaluation is done until AJAX requests)
* Multiple tables on the same view
* Non-``DatatableView`` showing a table powered by another view
* 100% customization for all cell values
* Ajax search
* Search data fields that aren't present on the table
* Customization hook for each row's JSON object
* Customization hook for full JSON response object
* Drop-in x-editable support, per-column
* Customizable table templates
* Easy Bootstrap integration
* Allows all normal dataTables.js and x-editable Javascript options
* Javascript global object to do automatic or late initialization for tables
* Library of common column markup options
* Full test suite

# Demos & Examples
There is an example project wrapped up inside of the ``tests`` component of the resuable app, which
can be executed using the following basic setup:

```bash
$ git clone https://github.com/pivotal-energy-solutions/django-datatable-view.git
$ cd django-datatable-view
$ mkvirtualenv datatableview
(datatableview)$ pip install -r requirements.txt
(datatableview)$ datatableview/tests/example_project/manage.py syncdb
(datatableview)$ datatableview/tests/example_project/manage.py runserver
```

The example project is configured to use a local sqlite3 database, and relies only on the ``django-datatable-view`` app itself.  In fact, it disables the normal ``django.contrib`` apps (except for ``django.contrib.staticfiles``, so that the dev server can serve the included statics) and disables all default middleware but the ``CommonMiddlware`` and ``CsrfViewMiddleware`` (the latter for supporting the x-editable demonstrations.)

A public online version of the example project can be found here:

http://django-datatable-view.appspot.com/

## Authors

* Tim Valenta
* Steven Klass


## Copyright and license

Copyright (c) 2012-2013 Pivotal Energy Solutions.  All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this work except in compliance with the License.
You may obtain a copy of the License in the LICENSE file, or at:

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
