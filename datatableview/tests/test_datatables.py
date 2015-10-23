# -*- encoding: utf-8 -*-
from inspect import isgenerator

from .testcase import DatatableViewTestCase
from .test_app import models
from ..exceptions import ColumnError
from ..datatables import Datatable, ValuesDatatable
from ..views import DatatableJSONResponseMixin
from .. import columns
from .. import utils

class DatatableTests(DatatableViewTestCase):
    def test_normalize_config(self):
        dt = Datatable([], '/')
        self.assertEqual(dt.config['hidden_columns'], [])
        self.assertEqual(dt.config['search_fields'], [])
        self.assertEqual(dt.config['unsortable_columns'], [])
        self.assertEqual(dt.config['search'], '')
        self.assertEqual(dt.config['start_offset'], 0)
        self.assertEqual(dt.config['page_length'], 25)
        self.assertEqual(dt.config['ordering'], None)

    def test_column_names_list_raises_unknown_columns(self):
        class DT(Datatable):
            class Meta:
                model = models.ExampleModel
                columns = ['fake']

        with self.assertRaises(ColumnError) as cm:
            dt = DT([], '/')
        self.assertEqual(str(cm.exception), "Unknown column name(s): ('fake',)")

    def test_column_names_list_finds_local_fields(self):
        class DT(Datatable):
            class Meta:
                model = models.ExampleModel
                columns = ['name']

        class NoError(BaseException):
            pass

        with self.assertRaises(NoError):
            dt = DT([], '/')
            raise NoError()

    def test_column_names_list_raises_related_columns(self):
        # This was the old way of including related data, but this is no longer supported
        class DT(Datatable):
            class Meta:
                model = models.ExampleModel
                columns = ['related__name']

        with self.assertRaises(ColumnError) as cm:
            dt = DT([], '/')
        self.assertEqual(str(cm.exception), "Unknown column name(s): ('related__name',)")

    def test_column_names_list_finds_related_fields(self):
        class DT(Datatable):
            related = columns.TextColumn("Related", ['related__name'])
            class Meta:
                model = models.ExampleModel
                columns = ['name', 'related']

        class NoError(BaseException):
            pass

        with self.assertRaises(NoError):
            dt = DT([], '/')
            raise NoError()

    def test_get_ordering_splits(self):
        # Verify empty has blank db-backed list and virtual list
        dt = Datatable([], '/')
        self.assertEqual(dt.get_ordering_splits(), ([], []))

        class DT(Datatable):
            fake = columns.TextColumn("Fake", sources=['get_absolute_url'])

            class Meta:
                model = models.ExampleModel
                columns = ['name', 'fake']

        # Verify a fake field name ends up separated from the db-backed field
        dt = DT([], '/', query_config={'iSortingCols': '1', 'iSortCol_0': '0', 'sSortDir_0': 'asc'})
        self.assertEqual(dt.get_ordering_splits(), (['name'], []))

        # Verify ['name', 'fake'] ordering sends 'name' to db sort list, but keeps 'fake' in manual
        # sort list.
        dt = DT([], '/', query_config={'iSortingCols': '2', 'iSortCol_0': '0', 'sSortDir_0': 'asc', 'iSortCol_1': '1', 'sSortDir_1': 'asc'})
        self.assertEqual(dt.get_ordering_splits(), (['name'], ['fake']))

        # Verify a fake field name as the sort column correctly finds no db sort fields
        dt = DT([], '/', query_config={'iSortingCols': '1', 'iSortCol_0': '1', 'sSortDir_0': 'asc'})
        self.assertEqual(dt.get_ordering_splits(), ([], ['fake']))

        # Verify ['fake', 'name'] ordering sends both fields to manual sort list
        dt = DT([], '/', query_config={'iSortingCols': '2', 'iSortCol_0': '1', 'sSortDir_0': 'asc', 'iSortCol_1': '0', 'sSortDir_1': 'asc'})
        self.assertEqual(dt.get_ordering_splits(), ([], ['fake', 'name']))

    def test_get_records_populates_cache(self):
        models.ExampleModel.objects.create(name="test name")
        queryset = models.ExampleModel.objects.all()

        dt = Datatable(queryset, '/')
        dt.get_records()
        self.assertIsNotNone(dt._records)
        records = dt._records

        # _records doesn't change when run again
        dt.get_records()
        self.assertEqual(dt._records, records)

    def test_populate_records_searches(self):
        obj1 = models.ExampleModel.objects.create(name="test name 1")
        obj2 = models.ExampleModel.objects.create(name="test name 2")
        queryset = models.ExampleModel.objects.all()

        class DT(Datatable):
            class Meta:
                model = models.ExampleModel
                columns = ['name']
        dt = DT(queryset, '/')

        # Sanity check for correct initial queryset
        dt.populate_records()
        self.assertIsNotNone(dt._records)
        self.assertEqual(list(dt._records), list(queryset))

        # Verify a search eliminates items from _records
        dt = DT(queryset, '/', query_config={'sSearch': 'test name 1'})
        dt.populate_records()
        self.assertIsNotNone(dt._records)
        self.assertEqual(list(dt._records), [obj1])

    def test_populate_records_sorts(self):
        obj1 = models.ExampleModel.objects.create(name="test name 1")
        obj2 = models.ExampleModel.objects.create(name="test name 2")
        queryset = models.ExampleModel.objects.all()

        class DT(Datatable):
            class Meta:
                model = models.ExampleModel
                columns = ['name']
        dt = DT(queryset, '/')

        # Sanity check for correct initial queryset
        dt.populate_records()
        self.assertIsNotNone(dt._records)
        self.assertEqual(list(dt._records), list(queryset))

        # Verify a sort changes the ordering of the records list
        dt = DT(queryset, '/', query_config={'iSortingCols': '1', 'iSortCol_0': '0', 'sSortDir_0': 'desc'})
        dt.populate_records()
        self.assertIsNotNone(dt._records)
        self.assertEqual(list(dt._records), [obj2, obj1])

    def test_populate_records_avoids_column_callbacks(self):
        obj1 = models.ExampleModel.objects.create(name="test name 1")
        queryset = models.ExampleModel.objects.all()
        class DT(Datatable):
            def preload_record_data(self, obj):
                raise Exception("Don't run this")
        dt = DT(queryset, '/')
        try:
            dt.populate_records()
        except Exception as e:
            if str(e) == "Don't run this":
                raise AssertionError("Per-row callbacks being executed!")
            raise

    def test_preload_record_data_calls_view(self):
        obj1 = models.ExampleModel.objects.create(name="test name 1")
        queryset = models.ExampleModel.objects.all()
        class Dummy(object):
            def preload_record_data(self, obj):
                raise Exception("We did it")
        dt = Datatable(queryset, '/', callback_target=Dummy())
        with self.assertRaises(Exception) as cm:
            dt.get_records()
        self.assertEqual(str(cm.exception), "We did it")

    def test_get_object_pk(self):
        obj1 = models.ExampleModel.objects.create(name="test name 1")
        queryset = models.ExampleModel.objects.all()
        dt = Datatable(queryset, '/')
        self.assertEqual(dt.get_object_pk(obj1), obj1.pk)

    def test_get_extra_record_data_passes_through_to_object_serialization(self):
        obj1 = models.ExampleModel.objects.create(name="test name 1")
        queryset = models.ExampleModel.objects.all()

        class DT(Datatable):
            def get_extra_record_data(self, obj):
                return {'custom': 'data'}

        dt = DT([], '/')
        data = dt.get_record_data(obj1)
        self.assertIn('_extra_data', data)
        self.assertIn('custom', data['_extra_data'])
        self.assertEqual(data['_extra_data']['custom'], 'data')

    def test_get_extra_record_data_passes_through_to_json_response(self):
        obj1 = models.ExampleModel.objects.create(name="test name 1")
        queryset = models.ExampleModel.objects.all()

        class DT(Datatable):
            def get_extra_record_data(self, obj):
                return {'custom': 'data'}

        class FakeRequest(object):
            GET = {'sEcho': 0}

        dt = DT(queryset, '/')
        view = DatatableJSONResponseMixin()
        view.request = FakeRequest()
        data = view.get_json_response_object(dt)
        self.assertIn('aaData', data)
        self.assertIn('DT_RowData', data['aaData'][0])
        self.assertEqual(data['aaData'][0]['DT_RowData'], {'custom': 'data'})

    def test_get_column_value_forwards_to_column_class(self):
        class CustomColumn1(columns.Column):
            def value(self, obj, **kwargs):
                return "first"

        class CustomColumn2(columns.Column):
            def value(self, obj, **kwargs):
                return "second"

        class DT(Datatable):
            fake1 = CustomColumn1("Fake1", sources=['get_absolute_url'])
            fake2 = CustomColumn2("Fake2", sources=['get_absolute_url'])

            class Meta:
                model = models.ExampleModel
                columns = ['name', 'fake1', 'fake2']

        obj1 = models.ExampleModel.objects.create(name="test name 1")
        queryset = models.ExampleModel.objects.all()
        dt = DT(queryset, '/')
        data = dt.get_record_data(obj1)
        self.assertIn('1', data)
        self.assertIn(data['1'], 'first')
        self.assertIn('2', data)
        self.assertIn(data['2'], 'second')

    def test_get_processor_method(self):
        class Dummy(object):
            def fake_callback(self):
                pass

        view = Dummy()

        # Test no callback given
        dt = Datatable([], '/')
        f = dt.get_processor_method(columns.Column("Fake", sources=['fake']), i=0)
        self.assertEqual(f, None)

        class DT(Datatable):
            def fake_callback(self):
                pass

        column = columns.Column("Fake", sources=['fake'], processor='fake_callback')

        # Test callback found on self
        dt = DT([], '/')
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, dt.fake_callback)

        # Test callback found on callback_target
        dt = Datatable([], '/', callback_target=view)
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, view.fake_callback)

    def test_get_processor_method_returns_direct_callable(self):
        def fake_callback():
            pass

        column = columns.Column("Fake", sources=[], processor=fake_callback)

        # Test no callback given
        dt = Datatable([], '/')
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, fake_callback)

    def test_get_processor_method_finds_implied_callback(self):
        class DummyNamed(object):
            def get_column_fake_data(self):
                pass

        class DummyIndexed(object):
            def get_column_0_data(self):
                pass

        class DummyBoth(object):
            def get_column_fake_data(self):
                pass

            def get_column_0_data(self):
                pass

        column = columns.Column("Fake", sources=[])
        column.name = 'fake'

        # Test implied named callback found first
        view = DummyNamed()
        dt = Datatable([], '/', callback_target=view)
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, view.get_column_fake_data)

        # Test implied named callback found first
        view = DummyIndexed()
        dt = Datatable([], '/', callback_target=view)
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, view.get_column_0_data)

        # Test implied named callback found first
        view = DummyBoth()
        dt = Datatable([], '/', callback_target=view)
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, view.get_column_fake_data)

        class DTNamed(Datatable):
            def get_column_fake_data(self):
                pass

        class DTIndexed(Datatable):
            def get_column_0_data(self):
                pass

        class DTBoth(Datatable):
            def get_column_fake_data(self):
                pass

            def get_column_0_data(self):
                pass


        # Test implied named callback found first
        dt = DTNamed([], '/')
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, dt.get_column_fake_data)

        # Test implied named callback found first
        dt = DTIndexed([], '/')
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, dt.get_column_0_data)

        # Test implied named callback found first
        dt = DTBoth([], '/')
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, dt.get_column_fake_data)

    def test_iter_datatable_yields_columns(self):
        class CustomColumn1(columns.Column):
            pass

        class CustomColumn2(columns.Column):
            pass

        class DT(Datatable):
            fake1 = CustomColumn1("Fake1", sources=['get_absolute_url'])
            fake2 = CustomColumn2("Fake2", sources=['get_absolute_url'])

            class Meta:
                model = models.ExampleModel
                columns = ['name', 'fake1', 'fake2']

        dt = DT([], '/')
        self.assertEqual(isgenerator(dt.__iter__()), True)
        self.assertEqual(list(dt), [dt.columns['name'], dt.columns['fake1'], dt.columns['fake2']])

    def test_search_term_basic(self):
        obj1 = models.ExampleModel.objects.create(name="test name 1")
        obj2 = models.ExampleModel.objects.create(name="test name 2")
        obj3 = models.ExampleModel.objects.create(name="test name 12")
        queryset = models.ExampleModel.objects.all()

        class DT(Datatable):
            class Meta:
                model = models.ExampleModel
                columns = ['name']

        dt = DT(queryset, '/', query_config={'sSearch': 'test'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj1, obj2, obj3])

        dt = DT(queryset, '/', query_config={'sSearch': 'name'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj1, obj2, obj3])

        dt = DT(queryset, '/', query_config={'sSearch': '1'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj1, obj3])

        dt = DT(queryset, '/', query_config={'sSearch': '2'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj2, obj3])

        dt = DT(queryset, '/', query_config={'sSearch': '12'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj3])

        dt = DT(queryset, '/', query_config={'sSearch': '3'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [])

    def test_search_multiple_terms_use_AND(self):
        obj1 = models.ExampleModel.objects.create(name="test name 1")
        obj2 = models.ExampleModel.objects.create(name="test name 2")
        obj3 = models.ExampleModel.objects.create(name="test name 12")
        queryset = models.ExampleModel.objects.all()

        class DT(Datatable):
            class Meta:
                model = models.ExampleModel
                columns = ['name']

        dt = DT(queryset, '/', query_config={'sSearch': 'test name'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj1, obj2, obj3])

        dt = DT(queryset, '/', query_config={'sSearch': 'test 1'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj1, obj3])

        dt = DT(queryset, '/', query_config={'sSearch': 'test 2'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj2, obj3])

        dt = DT(queryset, '/', query_config={'sSearch': 'test 12'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj3])

        dt = DT(queryset, '/', query_config={'sSearch': 'test 3'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [])

    def test_search_term_queries_all_columns(self):
        r1 = models.RelatedModel.objects.create(name="test related 1 one")
        r2 = models.RelatedModel.objects.create(name="test related 2 two")
        obj1 = models.ExampleModel.objects.create(name="test name 1", related=r1)
        obj2 = models.ExampleModel.objects.create(name="test name 2", related=r2)

        queryset = models.ExampleModel.objects.all()

        class DT(Datatable):
            related = columns.TextColumn("Related", ['related__name'])
            class Meta:
                model = models.ExampleModel
                columns = ['name', 'related']

        dt = DT(queryset, '/', query_config={'sSearch': 'test'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj1, obj2])

        dt = DT(queryset, '/', query_config={'sSearch': 'test name'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj1, obj2])

        dt = DT(queryset, '/', query_config={'sSearch': 'test 2'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj2])

        dt = DT(queryset, '/', query_config={'sSearch': 'related 2'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj2])

        dt = DT(queryset, '/', query_config={'sSearch': 'test one'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj1])

        dt = DT(queryset, '/', query_config={'sSearch': '2 two'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [obj2])

        dt = DT(queryset, '/', query_config={'sSearch': 'test three'})
        dt.populate_records()
        self.assertEquals(list(dt._records), [])


class ValuesDatatableTests(DatatableViewTestCase):
    def test_get_object_pk(self):
        obj1 = models.ExampleModel.objects.create(name="test name 1")
        queryset = models.ExampleModel.objects.all()
        dt = ValuesDatatable(queryset, '/')
        obj_data = queryset.values('pk')[0]
        self.assertEqual(dt.get_object_pk(obj_data), obj1.pk)
