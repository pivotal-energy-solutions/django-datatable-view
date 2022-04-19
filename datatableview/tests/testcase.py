# -*- coding: utf-8 -*-

from django.test import TestCase
from django.core.management import call_command
from django.apps import apps


class DatatableViewTestCase(TestCase):
    def _pre_setup(self):
        """
        Asks the management script to re-sync the database.  Having test-only models is a pain.
        """
        apps.clear_cache()
        call_command("loaddata", "initial_data", verbosity=0)
        super(DatatableViewTestCase, self)._pre_setup()
