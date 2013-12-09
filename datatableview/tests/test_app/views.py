from os import sep
import os.path
import re

from django.views.generic import TemplateView
from django.conf import settings

from datatableview.views import DatatableView, XEditableDatatableView

from test_app.models import ExampleModel

class IndexView(TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)

        # Try to determine if the user jumped the gun on testing things out
        db_works = True
        try:
            list(ExampleModel.objects.all()[:1])
        except:
            db_works = False
        context['db_works'] = db_works

        path, working_directory = os.path.split(os.path.abspath('.'))
        context['working_directory'] = working_directory
        context['os_sep'] = sep

        return context

class DemoMixin(object):
    description = """Missing description!"""
    implementation = """<pre>Missing implementation details!</pre>"""

    def get_template_names(self):
        """ Try the view's snake_case name, or else use default simple template. """
        name = self.__class__.__name__.replace("DatatableView", "")
        folder = "datatable"
        if name.endswith("XEditable"):
            folder = "xeditable"
            name = name.replace("XEditable", "")
        name = re.sub(r'([a-z]|[A-Z]+)(?=[A-Z])', r'\1_', name)
        return [os.path.join(folder, name.lower() + ".html"), "example_base.html"]

    def get_context_data(self, **kwargs):
        context = super(DemoMixin, self).get_context_data(**kwargs)
        context['implementation'] = self.implementation

        # Unwrap the lines of description text so that they don't linebreak funny after being put
        # through the ``linebreaks`` template filter.
        paragraphs = []
        p = []
        for line in self.__doc__.splitlines():
            line = line[4:].rstrip()
            if not line:
                paragraphs.append(p)
                p = []
            else:
                p.append(line)
        context['description'] = "\n\n".join(" ".join(p) for p in paragraphs)

        return context

class ZeroConfigurationDatatableView(DemoMixin, DatatableView):
    """
    If no columns are specified in the view's <code>datatable_options</code> atribute,
    <code>DatatableView</code> will use all of the model's local fields.

    This is a paragraph break
    """

    model = ExampleModel
    datatable_options = {}

    implementation = u"""
    <pre class="brush: python">
    # models.py
    class ZeroConfigurationDatatableView(DatatableView):
        model = ExampleModel
    </pre>

    <pre class="brush: python">
    # views.py
    class ZeroConfigurationDatatableView(DatatableView):
        model = ExampleModel
    </pre>
    """
