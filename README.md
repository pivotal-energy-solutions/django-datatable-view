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

* Python 2.7/3.5 or later
* [Django](http://www.djangoproject.com/) >= 1.11
* [dateutil](http://labix.org/python-dateutil) library for flexible, fault-tolerant date parsing.

# Getting Started Most basic

__Remember Django > 1.10 is not supported__

Install the package

    pip install django-datatable-view

Add `datatableview` to  `INSTALLED_APPS`

    INSTALLED_APPS = (
        ...
        'datatableview',
        ...
    )

Import the `DatatableView` in your views

    from datatableview.views import DatatableView

Create the view:

    class ZeroConfigurationDatatableView(DatatableView):
        model = Entry

Download `datatables` from [jquery datatables](https://datatables.net/download/index) and add them as static resources to your page

    <link rel="stylesheet" href="{% static 'css/jquery.dataTables.min.css' %}">
    <script type="text/javascript" charset="utf8" src="{% static 'js/jquery.dataTables.min.js' %}"></script>
    <script type="text/javascript" charset="utf8" src="{% static 'js/datatableview.js' %}"></script>
    <script type="text/javascript" charset="utf8">
        datatableview.auto_initialize = true;
    </script>

Then in your template add the `{{ datatable }}`:

    <div class="row">
        <div class="col-xs-12">
            <div class="table-responsive">
                {{ datatable }}
            </div>
        </div>
    </div>


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

# Documentation and Live Demos
Read the module documentation at http://django-datatable-view.readthedocs.org.

A public live demo server is in the works.  For version 0.8, we will continue to keep the live demo site alive at http://django-datatable-view.appspot.com/  Please note that 0.8 does not reflect the current state or direction of the project.

You can run the live demos locally from the included example project, using a few common setup steps.

```bash
$ git clone https://github.com/pivotal-energy-solutions/django-datatable-view.git
$ cd django-datatable-view
$ mkvirtualenv datatableview
(datatableview)$ pip install -r requirements.txt
(datatableview)$ datatableview/tests/example_project/manage.py migrate
(datatableview)$ datatableview/tests/example_project/manage.py loaddata initial_data
(datatableview)$ datatableview/tests/example_project/manage.py runserver
```

The example project is configured to use a local sqlite3 database, and relies on the ``django-datatable-view`` app itself, which is made available in the python path by simply running the project from the distributed directory root.


## Authors

* Autumn Valenta
* Steven Klass


## Copyright and license

Copyright (c) 2012-2018 Pivotal Energy Solutions.  All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this work except in compliance with the License.
You may obtain a copy of the License in the LICENSE file, or at:

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
