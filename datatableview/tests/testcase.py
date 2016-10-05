# -*- encoding: utf-8 -*-

import django
from django.test import TestCase
from django.core.management import call_command

if django.VERSION >= (1, 7):
    from django.test import override_settings
    from django.apps import apps
    migrate_command = 'migrate'
    initial_data_fixture = 'initial_data_modern'
    clear_app_cache = apps.clear_cache
else:
    from django.test.utils import override_settings
    from django.db.models import loading
    migrate_command = 'syncdb'
    initial_data_fixture = 'initial_data_legacy'
    def clear_app_cache():
        loading.cache.loaded = False


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
        clear_app_cache()
        call_command(migrate_command, interactive=False, verbosity=0)
        call_command('loaddata', initial_data_fixture, interactive=False, verbosity=0)
        super(DatatableViewTestCase, self)._pre_setup()
