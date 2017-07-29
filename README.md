# Datatable View

This package is used in conjunction with the jQuery plugin [DataTables](http://datatables.net/), and supports state-saving detection with [fnSetFilteringDelay](http://datatables.net/plug-ins/api).  The package consists of a class-based view, and a small collection of utilities for rendering table data from models.

[![PyPI Downloads][pypi-dl-image]][pypi-dl-link]
[![PyPI Version][pypi-v-image]][pypi-v-link]
[![Build Status][travis-image]][travis-link]
[![Documentation Status][rtfd-image]][rtfd-link]

[pypi-dl-link]: https://pypi.python.org/pypi/django-datatable-view
[pypi-dl-image]: https://img.shields.io/pypi/dm/django-datatable-view.png
[pypi-v-link]: https://pypi.python.org/pypi/django-datatable-view
[pypi-v-image]: https://img.shields.io/pypi/v/django-datatable-view.png
[travis-link]: https://travis-ci.org/pivotal-energy-solutions/django-datatable-view
[travis-image]: https://travis-ci.org/pivotal-energy-solutions/django-datatable-view.svg?branch=traviscl
[rtfd-link]: http://django-datatable-view.readthedocs.org/en/latest/?badge=latest
[rtfd-image]: https://readthedocs.org/projects/django-datatable-view/badge/?version=latest

Dependencies:

* [Django](http://www.djangoproject.com/) >= 1.8
* [dateutil](http://labix.org/python-dateutil) library for flexible, fault-tolerant date parsing.

# Features at a glance

* ``DatatableView``, a drop-in replacement for ``ListView`` that allows options to be specified for the datatable that will be rendered on the page.
* ``MultipleDatatableView`` for configurating multiple Datatable specifications on a single view
* ``ModelForm``-like declarative table design.
* Support for ``ValuesQuerySet`` execution mode instead of object instances
* Queryset caching between requests
* Customizable table headers
* Compound columns (columns representing more than one model field)
* Columns backed by methods or callbacks instead of model fields
* Easy related fields
* Automatic search and sort support
* Total control over cell contents (HTML, processing of raw values)
* Search data fields that aren't present on the table
* Support for DT_RowData
* Customization hook for full JSON response object
* Drop-in x-editable support, per-column
* Customizable table templates
* Easy Bootstrap integration
* Allows all normal dataTables.js and x-editable Javascript options
* Small library of common column markup processors
* Full test suite

# Quickstart
1. Install from PyPI 
```
pip install django-datatable-view
```
to intall directly from the repo
```
pip install git+git://github.com/pivotal-energy-solutions/django-datatable-view.git
```

2. Add to `INSTALLED_APPS`
```py
# settings.py
INSTALLED_APPS = [
    ...
    'datatableview',
]
```

3. create a simple view like this
```py
# views.py
class TestDataTable(DatatableView):
    template_name = 'textdatatable.html'
    model = Account
```

4. in your template render the table like this 
```
{% block content %}
    {{ datatable }}
{% endblock %}
```
also dont forget to include the `datatable.js` and `datatableview.js` as 
shown [here](http://django-datatable-view.appspot.com/javascript-initialization/)

5. initialize table using the following snippet
```javascript
// Standard initialization
var opts = {};
var datatable = datatableview.initialize($('.datatable'), opts);

// Get a reference to the new API object
var table = datatable.api();
```

# Documentation and Live Demos
Read the module documentation at http://django-datatable-view.readthedocs.org.

You can interact with live demos for the latest version at http://fixme.  For version 0.8, we will continue to keep the live demo site alive at http://django-datatable-view.appspot.com/

You can also run the live demos locally from the included example project, using a few setup steps.

```bash
$ git clone https://github.com/pivotal-energy-solutions/django-datatable-view.git
$ cd django-datatable-view
$ mkvirtualenv datatableview
(datatableview)$ pip install -r requirements.txt
(datatableview)$ datatableview/tests/example_project/manage.py syncdb
(datatableview)$ datatableview/tests/example_project/manage.py loaddata initial_data_modern
(datatableview)$ datatableview/tests/example_project/manage.py runserver
```

The example project is configured to use a local sqlite3 database, and relies only on the ``django-datatable-view`` app itself.  In fact, it disables the normal ``django.contrib`` apps (except for ``django.contrib.staticfiles``, so that the dev server can serve the included statics) and disables all default middleware except for ``CommonMiddlware`` and ``CsrfViewMiddleware`` (the latter for supporting the x-editable demonstrations.)


## Authors

* Tim Valenta
* Steven Klass


## Copyright and license

Copyright (c) 2012-2015 Pivotal Energy Solutions.  All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this work except in compliance with the License.
You may obtain a copy of the License in the LICENSE file, or at:

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
