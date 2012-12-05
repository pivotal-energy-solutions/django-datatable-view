# Datatable View

This package is used in conjunction with the jQuery plugin [DataTables](http://http://datatables.net/), and supports state-saving detection with [fnSetFilteringDelay](http://datatables.net/plug-ins/api).  The package consists of a class-based view, and a small collection of utilities for internal and external use.

## Usage

The basic template for usage in a view is shown below.

    # views.py
    
    from datatableview.views import DatatableView
    from myapp.models import MyModel
    
    class MyListView(DatatableView):
        datatable_options = {
            'columns': ['field_name1', 'field_name2'],
        }
        
        def get_queryset(self):
            return MyModel.objects.filter(user=self.request.user)
    
`DatatableView` inherits from the generic `ListView` built-in view.  This means that as a foundation, a datatable-enhanced view requires very little extra configuration to get off the ground.  Methods such as `get_queryset()` function normally.

The simplest way to output this simple table as HTML in a template is to use the `datatable` context variable, which `DatatableView` makes available via `get_context_data()`.  (So if you override `get_context_data()`, be sure to call `super()`!).

Thus, in your template ("mymodel_list.html" if we're following the standard ListView template naming scheme), you would echo the value where you want the table to appear:

    {# mymodel_list.html #}
    
    {% block media %}
        <script type="text/javascript" src="{{ STATIC_URL }}js/jquery.dataTable.js"></script>
        <script type="text/javascript" src="{{ STATIC_URL }}js/datatableview.js"></script>
    {% endblock %}
    
    {% block content %}
        {{ datatable }}
    {% endblock %}
    
The `datatable` context variable is a basic object that has a unicode representation matching the configuration options specified in the originating view.  The output is a table skeleton of just table headers, annotated with information that the provided `datatableview.js` file will use to
detect and bootstrap the table's interactive features, including fetching the first batch of AJAX data.

Each of the generated datatable `<th>` elements have a custom attribute "data-name", whose values are just the header name put through the `slugify` template filter.  This provides a simple way for CSS to be provided on the page to specify style attributes such as column width:
    
    .datatable th[data-name="slugified-field-name"] {
        width: 20%;
    }

## Column declaration

While the first natural step is to display columns backed by concrete fields on your model, it doesn't take long to find yourself requiring richer output information.

#### Changing the column's display name

The column header's displayed title is by default a mangling of the field name given in the column options.  For example, "field_name1" turns into "Field name" if left alone.  To give it an arbitrary label better suited for the frontend, change the entry in the column options to a 2-tuple of the friendly name and the model field name:

    datatable_options = {
        'columns': [
            ("Friendly Name", 'field_name1'),
            'field_name2',
        ],
    }
    
`field_name2` is left to behave normally, while `field_name1` will display on the table as "Friendly Name".

Django's relationship-spanning lookups can be used here as well:

    datatable_options = {
        'columns': [
            ('Company Name', 'company__name'),
            'field_name2',
        ]
    }

#### Compound columns

When a column in the table is actually built using data from multiple model fields, such as a series of fields that together form a full address, the column options can be given to provide the necessary hints for the searching logic to do the right thing.

Since multiple model fields together aren't likely to make a very good table header label, you should use the format in the section just above, where you provide a custom name.

Using the example of a compound address table column:

    datatable_options = {
        'columns': [
            ('Address', ['street_line1', 'street_line2', 'city', 'state']),
            'field_name2',
        ],
    }
    
This configuration will produce a column titled "Address", whose contents is all of the database field values joined with a space.  That format might not be good enough for something as punctuated as an address should be, so you should consult the [Customizing column output](#customizing-column-output) section below to understand how to manually format the table cell contents beyond this default.  This configuration, however, is fully capable of providing database-backed searching features for the listed columns.

#### Pure virtual columns

If you need a table column that has no specific database-backed field, whether because it's a purely computed value from a model's method or for some other complex manipulation, a virtual column name can be used in the options:

    datatable_options = {
        'columns': [
            'Fictitious',
            'field_name2',
        ],
    }

In this example the column called "Fictitious" is capitalized to help keep clear its virtual nature.  When the view logic goes to interpret the column options, it will find that "Fictitious" is not a valid field name, given the model defined by the view (or taken from the view's queryset).  The column has no database fields to back it, which means this column currently has no way to provide its value.

Continue to the next section [Customizing column output](#customizing-column-output) to create a mechanism for providing arbitrary column data.

#### Customizing column output

When each resulting record returned by the queryset is serialized to JSON for transport back to the client, each column has a chance to modify its displayed value.

Each column name (whether concrete, compound, or virtual) will be used to check the view for callback methods.  If the method exists, it will be called and passed the instance of the object being rendered.  The method can return whatever it wants.  If the column is database-backed by a model field, one would expect the output to simply be some lightly decorated version of the same thing.

A contrived example following from the original configuration sample:

    class MyListView(DatatableView):
        datatable_options = {
            'columns': [
                ('Friendly Name', 'field_name1'),
                'field_name2',
            ],
        }
        
        # ... get_queryset() or model should be defined
        
        def get_column_Friendly_Name_data(self, instance, *args, **kwargs):
            return "{:.2f}".format(instance.field_name1)
        
        def get_column_field_name2_data(self, instance, *args, **kwargs):
            return "<em>{}</em>".format(self.field_name2)

As shown, methods in the form `get_column_FIELD_NAME_data()` can be defined on the view to override the output of the column.

IMPORTANT: In the case of these two sample fields, both are concrete, being backed by real database fields.  The data returned by these methods are consequently for display purposes.  Any time that concrete model fields back a column, those fields are used for sorting and searching, not the output of the callback methods.

As demonstrated in the example, it is the actual column name that is used for the callback method naming style, where case is unmodified and non-alphanumeric characters are collapsed to underscores.  If a friendly name is "Completion: Percentage", the mangled name used for method lookup would be "Completion_Percentage", ultimately pointing to a method called `get_column_Completion_Percentage_data()`.

NOTE: These methods should take the `*args` and `**kwargs` argument names for good practice.  Their use is described in the following section [Handling expensive data generation](#handling-expensive-data-generation).

If ever the name mangling is unintuitive or unnecessarily complex, callback names can also be given via the column's 0-based index.  In the example above, the method names could could instead be given as `get_column_0_data()` and `get_column_1_data()` respectively.

Alternatively, columns can explicitly declare a method name as part of the column configuration, using a 3-tuple instead of a 2-tuple:

    class MyListView(DatatableView):
        datatable_options = {
            'columns': [
                ('Friendly Name', 'field_name1', 'get_friendly_data'),
                'field_name2',
            ],
        }
        
        # ...
        
        def get_friendly_data(self, instance, *args, **kwargs):
            return "{:.2f}".format(instance.field_name1) 

If the callback name in the configuration (e.g., `"get_friendly_data"`) were a full callable function instead of a string, the function would be used directly, as opposed to looking up any method on the view itself.

Finally, a purely virtual table column can also declare an explicit callback name using the 3-tuple pattern:

    class MyListView(DatatableView):
        datatable_options = {
            'columns': [
                ('Fictitious', None, 'get_fictitious_data'),
                'field_name2',
            ],
        }
        
        # ...
        
        def get_fictitious_data(self, instance, *args, **kwargs):
            return instance.get_generated_data()

Note that because the column is completely virtual and has no model fields backing it, `None` is provided in the place of a field name (or list of field names).

#### Handling expensive data generation

The callback methods described in [Customizing column output](#customizing-column-output) are very helpful for generating interactive data columns, such as links to deeper views, cross links to other sections of the site, or just computed mashups of data not strictly represented in any set of columns.

If multiple of the callback methods needs to do some expensive computation, each model instance (or record, in the terminology of the frontend datatable) can preload arbitrary values that will be sent to all of the view's data-supplying callback methods, either as `*args` or `**kwargs`, depending on how you prefer your implementation.

The special method `preload_record_data()` can return these values, computed once per record and passed to the various callbacks without slamming the database or CPU any heavier than expected:

    class MyListView(DatatableView):
        datatable_options = {
            'columns': [
                ('Fictitious', None, 'get_fictitious_data'),
                'field_name2',
            ],
        }
        
        # ...
        
        def preload_record_data(self, instance):
            users = instance.get_authorized_users()
            
            return (users,)
        
        def get_fictitious_data(self, instance, users, *args, **kwargs):
            return instance.get_generated_data(users)

In this example, `preload_record_data()` creates a value, presumably some kind of iterable of User objects, and returns it as a 1-tuple.  This 1-tuple will be expanded and sent to all callbacks, which led us to change our callback signature to include a `users` argument.

Alternatively, a tuple with more elements can be returned with whatever data is crunched:

    # ...
    def preload_record_data(self, instance):
        users = instance.get_authorized_users()
        groups = instance.get_authorized_groups()
        
        return (users, groups)
    
    def get_fictitious_data(self, instance, users, groups, *args, **kwargs):
        return instance.get_generated_data(users)

A callback is of course not required to use the data sent to it, since pre-crunched data might only be relevant to a handful of the callbacks.

If the object returned by `preload_record_data()` is a dictionary, not a tuple or list, it will be instead unpacked as the `**kwargs` for the callback methods.

Currently the two return types can not be mixed.

## Custom table rendering

By default, a DatatableView includes an object in the context called `datatable`, whose unicode rendering is the table skeleton.  Together with the supplied generic javascript file, the datatable is automatically brought to life according to the view's configuration.

If the table needs custom rendering, you can instead iterate over the `datatable` object in the template.  An equivalent to the default skeleton can be rendered in this style by using the following template HTML:

    # object_list.html
    
    {# ... #}
    <table class="datatable" data-url="{{ datatable.url }}">
        <tr>
            {% for name, attributes in datatable %}
            <th data-name="name|slugify" {{ attributes }}>{{ name }}</th>
            {% endfor %}
        </tr>
    </table>

The table should provide the class "datatable" for the provided datatableview.js code to pick up on it.  If desired, you can omit the classname and bootstrap the datatable yourself with the skeleton provided.  More Javascript methods will be made available in the future to accommodate that strategy.

The `table`'s "data-url" attribute is the url that dataTables.js will use to fetch the ajax data.  By default this is just the value of ``request.path``, pointing back to the original view.

The `th` "data-name" attribute isn't required for any dataTables.js functionality, but it provides a useful CSS selector hook for styling column widths, etc.

the `attributes` value is a pre-rendered HTML string of custom data-* attributes that provide configuration details to datatableview.js when it detects the datatable skeleton, such as sorting being enabled or disabled.
