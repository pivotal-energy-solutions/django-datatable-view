# -*- encoding: utf-8 -*-

from django.test import TestCase
from django.test import override_settings
from django.core.management import call_command
from django.apps import apps


@override_settings(INSTALLED_APPS=[
    'datatableview',
    'datatableview.tests.test_app',
    'datatableview.tests.example_project.example_project.example_app',
])
class DatatableViewTestCase(TestCase):
    def _pre_setup(self):
        """
        Asks the management script to re-sync the database.  Having test-only models is a pain.
        """
        apps.clear_cache()
        call_command('migrate', interactive=False, verbosity=0)
        call_command('loaddata', 'initial_data', verbosity=0)
        super(DatatableViewTestCase, self)._pre_setup()
