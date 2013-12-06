from django.test import TestCase
from django.core.management import call_command
from django.db.models import loading

class DatatableViewTestCase(TestCase):
    def _pre_setup(self):
        """
        Asks the management script to re-sync the database.  Having test-only models is a pain.
        """
        loading.cache.loaded = False
        call_command('syncdb', interactive=False, verbosity=0)
        super(DatatableViewTestCase, self)._pre_setup()
