from .testcase import DatatableViewTestCase
from .test_app import models
from .. import utils

def get_structure(columns, opts):
    return utils.get_datatable_structure('/', dict(opts, columns=columns), model=models.ExampleModel)

class UtilsTests(DatatableViewTestCase):
    def test_get_first_orm_bit(self):
        """  """
        self.assertEqual(utils.get_first_orm_bit('field'), 'field')
        self.assertEqual(utils.get_first_orm_bit('field__otherfield'), 'field')
        self.assertEqual(utils.get_first_orm_bit(["Pretty Name", 'field']), 'field')
        self.assertEqual(utils.get_first_orm_bit(["Pretty Name", 'field', "callback"]), 'field')
        self.assertEqual(utils.get_first_orm_bit(["Pretty Name", 'field__otherfield']), 'field')
        self.assertEqual(utils.get_first_orm_bit(["Pretty Name", 'field__otherfield', "callback"]), 'field')

    def test_resolve_orm_path_local(self):
        """ Verifies that references to a local field on a model are returned. """
        field = utils.resolve_orm_path(models.ExampleModel, 'name')
        self.assertEqual(field, models.ExampleModel._meta.get_field_by_name('name')[0])

    def test_resolve_orm_path_fk(self):
        """ Verify that ExampleModel->RelatedModel.name == RelatedModel.name """
        remote_field = utils.resolve_orm_path(models.ExampleModel, 'related__name')
        self.assertEqual(remote_field, models.RelatedModel._meta.get_field_by_name('name')[0])

    def test_resolve_orm_path_reverse_fk(self):
        """ Verify that ExampleModel->>>ReverseRelatedModel.name == ReverseRelatedModel.name """
        remote_field = utils.resolve_orm_path(models.ExampleModel, 'reverserelatedmodel__name')
        self.assertEqual(remote_field, models.ReverseRelatedModel._meta.get_field_by_name('name')[0])

    def test_resolve_orm_path_m2m(self):
        """ Verify that ExampleModel->>>RelatedM2MModel.name == RelatedM2MModel.name """
        remote_field = utils.resolve_orm_path(models.ExampleModel, 'relateds__name')
        self.assertEqual(remote_field, models.RelatedM2MModel._meta.get_field_by_name('name')[0])

    def test_split_real_fields(self):
        """ Verifies that the first non-real field causes a break in the field list. """
        model = models.ExampleModel

        # All-real fields
        real, fake = utils.split_real_fields(model, ['name', 'date_created'])
        self.assertEqual(real, ['name', 'date_created'])
        self.assertEqual(fake, [])

        # No real fields
        real, fake = utils.split_real_fields(model, ['fake1', 'fake2'])
        self.assertEqual(real, [])
        self.assertEqual(fake, ['fake1', 'fake2'])

        # Real first, fake last
        real, fake = utils.split_real_fields(model, ['name', 'fake'])
        self.assertEqual(real, ['name'])
        self.assertEqual(fake, ['fake'])
        
        # Fake first, real last
        real, fake = utils.split_real_fields(model, ['fake', 'name'])
        self.assertEqual(real, [])
        self.assertEqual(fake, ['fake', 'name'])
        
    def test_filter_real_fields(self):
        model = models.ExampleModel
        fields = [
            'name',
            ('name',),
            ("Pretty Name", 'name'),
            ("Pretty Name", 'name', 'callback'),
        ]
        fakes = [
            'fake',
            ("Pretty Name", 'fake'),
            ("Pretty Name", 'fake', 'callback'),
            None,
            ("Pretty Name", None),
            ("Pretty Name", None, 'callback'),
        ]
        db_fields, virtual_fields = utils.filter_real_fields(model, fields + fakes,
                                                             key=utils.get_first_orm_bit)

        self.assertEqual(db_fields, fields)
        self.assertEqual(virtual_fields, fakes)

    def test_structure_ordering(self):
        """ Verifies that the structural object correctly maps configuration values. """
        # Verify basic ordering
        columns = [
            'name',
        ]
        structure = get_structure(columns, { 'ordering': ['name'] })
        self.assertEqual(structure.ordering['name'].direction, 'asc')
        structure = get_structure(columns, { 'ordering': ['+name'] })
        self.assertEqual(structure.ordering['name'].direction, 'asc')
        structure = get_structure(columns, { 'ordering': ['-name'] })
        self.assertEqual(structure.ordering['name'].direction, 'desc')

        # Verify compound ordering is preserved
        columns = [
            'id',
            'name',
        ]
        structure = get_structure(columns, { 'ordering': ['name', 'id'] })
        self.assertEqual(structure.ordering['name'].order, 0)
        self.assertEqual(structure.ordering['id'].order, 1)

        # Verify non-real field ordering is recognized when column is defined
        columns = [
            'fake',
        ]
        structure = get_structure(columns, { 'ordering': ['fake'] })
        self.assertEqual(structure.ordering['fake'].direction, 'asc')
        structure = get_structure(columns, { 'ordering': ['+fake'] })
        self.assertEqual(structure.ordering['fake'].direction, 'asc')
        structure = get_structure(columns, { 'ordering': ['-fake'] })
        self.assertEqual(structure.ordering['fake'].direction, 'desc')

        # Verify invalid ordering names are not included
        columns = [
            'name',
        ]
        structure = get_structure(columns, { 'ordering': ['fake', 'name'] })
        self.assertIn('name', structure.ordering)
        self.assertNotIn('fake', structure.ordering)

    def test_structure_data_api(self):
        """
        Verifies that unsortable_columns, hidden_columns, and ordering all add expected data-* API
        attributes
        """
        columns = [
            'id',
            'name',
        ]
        structure = get_structure(columns, {})
        self.assertEqual(structure.get_column_attributes('name')['data-visible'], 'true')
        self.assertEqual(structure.get_column_attributes('name')['data-sortable'], 'true')
        structure = get_structure(columns, { 'hidden_columns': ['name'] })
        self.assertEqual(structure.get_column_attributes('name')['data-visible'], 'false')
        self.assertEqual(structure.get_column_attributes('name')['data-sortable'], 'true')
        structure = get_structure(columns, { 'unsortable_columns': ['name'] })
        self.assertEqual(structure.get_column_attributes('name')['data-visible'], 'true')
        self.assertEqual(structure.get_column_attributes('name')['data-sortable'], 'false')
        structure = get_structure(columns, { 'hidden_columns': ['name'], 'unsortable_columns': ['name'] })
        self.assertEqual(structure.get_column_attributes('name')['data-visible'], 'false')
        self.assertEqual(structure.get_column_attributes('name')['data-sortable'], 'false')
        structure = get_structure(columns, { 'ordering': ['-name', 'id'] })
        self.assertEqual(structure.get_column_attributes('id')['data-sorting'], '1,0,asc')
        self.assertEqual(structure.get_column_attributes('name')['data-sorting'], '0,1,desc')

    def test_structure_automatic_pretty_names(self):
        """ Verify columns missing Pretty Names receive one based on their field name. """
        columns = [
            ('Primary Key', 'id'),
            'name',
        ]
        structure = get_structure(columns, {})
        column_info = structure.get_column_info()

        self.assertEqual(column_info[0].pretty_name, "Primary Key")

        name_field = models.ExampleModel._meta.get_field_by_name('name')[0]
        self.assertEqual(column_info[1].pretty_name, name_field.name)

    def test_structure_is_iterable(self):
        """ Verify structure object can be iterated for each column definition. """
        columns = [
            'id',
            'name',
            'fake',
        ]
        structure = get_structure(columns, {})
        self.assertEqual(len(list(structure)), len(columns))

    def test_options_use_default_to_local_fields(self):
        """ Verifies that no columns specified in options means showing all local fields. """
        opts = {}
        options = utils.DatatableOptions(models.ExampleModel, {}, **opts)
        local_field_names = [(f.verbose_name, f.name) for f in models.ExampleModel._meta.local_fields]
        self.assertEqual(options.columns, local_field_names)

    def test_options_use_defaults(self):
        """ Verifies that no options normalizes to the default set. """
        options = utils.DatatableOptions(models.ExampleModel, {})
        self.assertEqual(options, dict(utils.DEFAULT_OPTIONS, columns=options.columns))

    def test_options_normalize_values(self):
        """ Verifies that the options object fixes bad values. """
        model = models.ExampleModel
        opts = {
            'search_fields': None,
            'unsortable_columns': None,
            'hidden_columns': None,
        }
        options = utils.DatatableOptions(model, {}, **opts)
        self.assertEqual(options.search_fields, [])
        self.assertEqual(options.unsortable_columns, [])
        self.assertEqual(options.hidden_columns, [])

        data = { utils.OPTION_NAME_MAP['start_offset']: -5 }
        options = utils.DatatableOptions(model, data)
        self.assertEqual(options.start_offset, 0)
        data = { utils.OPTION_NAME_MAP['start_offset']: 'not a number' }
        options = utils.DatatableOptions(model, data)
        self.assertEqual(options.start_offset, 0)

        data = { utils.OPTION_NAME_MAP['page_length']: -5 }
        options = utils.DatatableOptions(model, data)
        self.assertEqual(options.page_length, utils.MINIMUM_PAGE_LENGTH)
        data = { utils.OPTION_NAME_MAP['page_length']: -1 }  # special case for dataTables.js
        options = utils.DatatableOptions(model, data)
        self.assertEqual(options.page_length, -1)
        data = { utils.OPTION_NAME_MAP['page_length']: 'not a number' }
        options = utils.DatatableOptions(model, data)
        self.assertEqual(options.page_length, utils.DEFAULT_OPTIONS['page_length'])

    def test_options_sorting_validation(self):
        """ Verifies that sorting options respect configuration. """
        model = models.ExampleModel
        opts = {
            'columns': [
                'id',
                'date_created',
                'name',
            ],
            'ordering': ['name', 'id'],
            'unsortable_columns': ['date_created'],
        }

        # Invalid sort number means use default sorting
        data = { utils.OPTION_NAME_MAP['num_sorting_columns']: 'not a number' }
        options = utils.DatatableOptions(model, data, **opts)
        self.assertEqual(options.ordering, ['name', 'id'])

        # Invalid sort index means no sorting for that sorting priority
        data = {
            utils.OPTION_NAME_MAP['num_sorting_columns']: '2',
            (utils.OPTION_NAME_MAP['sort_column'] % 0): '999',  # bad column index
            (utils.OPTION_NAME_MAP['sort_column_direction'] % 0): 'asc',
            (utils.OPTION_NAME_MAP['sort_column'] % 1): '2',
            (utils.OPTION_NAME_MAP['sort_column_direction'] % 1): 'asc',
        }
        options = utils.DatatableOptions(model, data, **opts)
        self.assertEqual(options.ordering, ['name'])

        # Sort requested for unsortable column rejects sorting
        data = {
            utils.OPTION_NAME_MAP['num_sorting_columns']: '2',
            (utils.OPTION_NAME_MAP['sort_column'] % 0): '1',  # unsortable column index
            (utils.OPTION_NAME_MAP['sort_column_direction'] % 0): 'asc',
            (utils.OPTION_NAME_MAP['sort_column'] % 1): '0',
            (utils.OPTION_NAME_MAP['sort_column_direction'] % 1): 'asc',
        }
        options = utils.DatatableOptions(model, data, **opts)
        self.assertEqual(options.ordering, ['id'])

        # Invalid sort direction rejects sorting
        data = {
            utils.OPTION_NAME_MAP['num_sorting_columns']: '2',
            (utils.OPTION_NAME_MAP['sort_column'] % 0): '2',
            (utils.OPTION_NAME_MAP['sort_column_direction'] % 0): 'bad direction',  # unusable value
            (utils.OPTION_NAME_MAP['sort_column'] % 1): '0',
            (utils.OPTION_NAME_MAP['sort_column_direction'] % 1): 'asc',
        }
        options = utils.DatatableOptions(model, data, **opts)
        self.assertEqual(options.ordering, ['id'])

    def test_options_normalize_virtual_columns_to_special_names(self):
        """
        Verifies that virtual field receives index-based synonym to denote special conditions that
        will affect sorting/searching behavior.
        """
        model = models.ExampleModel
        opts = {
            'columns': [
                'id',
                'pk',  # 'pk' is technically not a real field, so it registers as fake!
                'fake',
            ],
        }
        data = {
            utils.OPTION_NAME_MAP['num_sorting_columns']: '3',
            (utils.OPTION_NAME_MAP['sort_column'] % 0): '0',
            (utils.OPTION_NAME_MAP['sort_column_direction'] % 0): 'desc',
            (utils.OPTION_NAME_MAP['sort_column'] % 1): '1',
            (utils.OPTION_NAME_MAP['sort_column_direction'] % 1): 'desc',
            (utils.OPTION_NAME_MAP['sort_column'] % 2): '2',
            (utils.OPTION_NAME_MAP['sort_column_direction'] % 2): 'asc',
        }
        options = utils.DatatableOptions(model, data, **opts)
        self.assertEqual(options.ordering, ['-id', '-!1', '!2'])
