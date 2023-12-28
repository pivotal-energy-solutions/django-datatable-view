# -*- coding: utf-8 -*-
import datetime
from inspect import isgenerator

from django.apps import apps

from .testcase import DatatableViewTestCase
from datatableview.exceptions import ColumnError
from datatableview.datatables import Datatable, ValuesDatatable
from datatableview.views import DatatableJSONResponseMixin, DatatableView
from datatableview.columns import TextColumn, Column, BooleanColumn

ExampleModel = apps.get_model("test_app", "ExampleModel")
RelatedModel = apps.get_model("test_app", "RelatedModel")


class DatatableTests(DatatableViewTestCase):
    def test_normalize_config(self):
        dt = Datatable([], "/")
        dt.configure()
        self.assertEqual(dt.config["hidden_columns"], [])
        self.assertEqual(dt.config["search_fields"], [])
        self.assertEqual(dt.config["unsortable_columns"], [])
        self.assertEqual(dt.config["search"], set())
        self.assertEqual(dt.config["start_offset"], 0)
        self.assertEqual(dt.config["page_length"], 25)
        self.assertEqual(dt.config["ordering"], None)

    def test_column_names_list_raises_unknown_columns(self):
        class DT(Datatable):
            class Meta:
                model = ExampleModel
                columns = ["fake"]

        dt = DT([], "/")
        with self.assertRaises(ColumnError) as cm:
            dt.configure()
        self.assertEqual(str(cm.exception), "Unknown column name(s): ('fake',)")

    def test_column_names_list_finds_local_fields(self):
        class DT(Datatable):
            class Meta:
                model = ExampleModel
                columns = ["name"]

        class NoError(BaseException):
            pass

        with self.assertRaises(NoError):
            dt = DT([], "/")
            raise NoError()

    def test_column_names_list_raises_related_columns(self):
        # This was the old way of including related data, but this is no longer supported
        class DT(Datatable):
            class Meta:
                model = ExampleModel
                columns = ["related__name"]

        dt = DT([], "/")
        with self.assertRaises(ColumnError) as cm:
            dt.configure()
        self.assertEqual(str(cm.exception), "Unknown column name(s): ('related__name',)")

    def test_column_names_list_finds_related_fields(self):
        class DT(Datatable):
            related = TextColumn("Related", ["related__name"])

            class Meta:
                model = ExampleModel
                columns = ["name", "related"]

        class NoError(BaseException):
            pass

        with self.assertRaises(NoError):
            dt = DT([], "/")
            raise NoError()

    def test_get_ordering_splits(self):
        # Verify empty has blank db-backed list and virtual list
        dt = Datatable([], "/")
        dt.configure()
        self.assertEqual(dt.get_ordering_splits(), ([], []))

        class DT(Datatable):
            fake = TextColumn("Fake", sources=["get_absolute_url"])

            class Meta:
                model = ExampleModel
                columns = ["name", "fake"]

        # Verify a fake field name ends up separated from the db-backed field
        dt = DT(
            [], "/", query_config={"order[0][column]": "0", "order[0][dir]": "asc"}
        )  # iSortingCols': '1',
        dt.configure()
        self.assertEqual(dt.get_ordering_splits(), (["name"], []))

        # Verify ['name', 'fake'] ordering sends 'name' to db sort list, but keeps 'fake' in manual
        # sort list.
        dt = DT(
            [],
            "/",
            query_config={
                "order[0][column]": "0",
                "order[0][dir]": "asc",
                "order[1][column]": "1",
                "order[1][dir]": "asc",
            },
        )  # 'iSortingCols': '2',
        dt.configure()
        self.assertEqual(dt.get_ordering_splits(), (["name"], ["fake"]))

        # Verify a fake field name as the sort column correctly finds no db sort fields
        dt = DT(
            [], "/", query_config={"order[0][column]": "1", "order[0][dir]": "asc"}
        )  # 'iSortingCols': '1',
        dt.configure()
        self.assertEqual(dt.get_ordering_splits(), ([], ["fake"]))

        # Verify ['fake', 'name'] ordering sends both fields to manual sort list
        dt = DT(
            [],
            "/",
            query_config={
                "order[0][column]": "1",
                "order[0][dir]": "asc",
                "order[1][column]": "0",
                "order[1][dir]": "asc",
            },
        )  # 'iSortingCols': '2',
        dt.configure()
        self.assertEqual(dt.get_ordering_splits(), ([], ["fake", "name"]))

    def test_get_records_populates_cache(self):
        ExampleModel.objects.create(name="test name")
        queryset = ExampleModel.objects.all()

        dt = Datatable(queryset, "/")
        dt.get_records()
        self.assertIsNotNone(dt._records)
        records = dt._records

        # _records doesn't change when run again
        dt.get_records()
        self.assertEqual(dt._records, records)

    def test_populate_records_searches(self):
        obj1 = ExampleModel.objects.create(name="test name 1", value=False)
        obj2 = ExampleModel.objects.create(name="test name 2", value=True)
        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            class Meta:
                model = ExampleModel
                columns = ["name", "value"]

        dt = DT(queryset, "/")

        # Sanity check for correct initial queryset
        dt.populate_records()
        self.assertIsNotNone(dt._records)
        self.assertEqual(list(dt._records), list(queryset))

        # Verify a search eliminates items from _records
        dt = DT(queryset, "/", query_config={"search[value]": "test name 1"})
        dt.populate_records()
        self.assertIsNotNone(dt._records)
        self.assertEqual(list(dt._records), [obj1])

    def test_populate_records_sorts(self):
        obj1 = ExampleModel.objects.create(name="test name 1")
        obj2 = ExampleModel.objects.create(name="test name 2")
        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            class Meta:
                model = ExampleModel
                columns = ["name"]

        dt = DT(queryset, "/")

        # Sanity check for correct initial queryset
        dt.populate_records()
        self.assertIsNotNone(dt._records)
        self.assertEqual(list(dt._records), list(queryset))

        # Verify a sort changes the ordering of the records list
        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "desc"}
        )  # # 'iSortingCols': '1',
        dt.populate_records()
        self.assertIsNotNone(dt._records)
        self.assertEqual(list(dt._records), [obj2, obj1])

    def test_populate_records_avoids_column_callbacks(self):
        obj1 = ExampleModel.objects.create(name="test name 1")
        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            def preload_record_data(self, obj):
                raise Exception("Don't run this")

        dt = DT(queryset, "/")
        try:
            dt.populate_records()
        except Exception as e:
            if str(e) == "Don't run this":
                raise AssertionError("Per-row callbacks being executed!")
            raise

    def test_preload_record_data_calls_view(self):
        obj1 = ExampleModel.objects.create(name="test name 1")
        queryset = ExampleModel.objects.all()

        class Dummy(object):
            def preload_record_data(self, obj):
                raise Exception("We did it")

        dt = Datatable(queryset, "/", callback_target=Dummy())
        with self.assertRaises(Exception) as cm:
            dt.get_records()
        self.assertEqual(str(cm.exception), "We did it")

    def test_sort_defaults_to_meta_ordering(self):
        # Defined so that 'pk' order != 'name' order
        obj1 = ExampleModel.objects.create(name="b")
        obj2 = ExampleModel.objects.create(name="a")
        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            name = TextColumn("Name", sources=["name"])

            class Meta:
                model = ExampleModel
                columns = ["name"]
                ordering = ["name"]

        dt = DT(queryset, "/")
        dt.populate_records()
        self.assertEqual(dt.get_ordering_splits(), (["name"], []))
        self.assertEqual(list(dt._records), [obj2, obj1])

        # this is to keep DatatableView class from overriding the Meta ordering in Datatable
        class DTV(DatatableView):
            datatable_class = DT
            model = ExampleModel

        dtv = DTV().get_datatable(url="/")
        self.assertIn(
            '<th data-name="name" data-config-sortable="true" data-config-sorting="0,0,asc" data-config-visible="true">Name</th>',
            dtv.__str__(),
        )

        class DT(Datatable):
            name = TextColumn("Name", sources=["name"])

            class Meta:
                model = ExampleModel
                columns = ["name"]
                ordering = ["-name"]

        dt = DT(queryset, "/")
        dt.populate_records()
        self.assertEqual(dt.get_ordering_splits(), (["-name"], []))
        self.assertEqual(list(dt._records), [obj1, obj2])

    def test_sort_prioritizes_db_source(self):
        # Defined so that 'pk' order != 'name' order
        obj1 = ExampleModel.objects.create(name="test name 2")
        obj2 = ExampleModel.objects.create(name="test name 1")
        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            name = TextColumn("Name", sources=["name"])

            class Meta:
                model = ExampleModel
                columns = ["name"]
                ordering = ["pk"]

        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "asc"}
        )  # 'iSortingCols': '1',
        dt.populate_records()
        self.assertEqual(dt.get_ordering_splits(), (["name"], []))
        self.assertEqual(list(dt._records), [obj2, obj1])

        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "desc"}
        )  # 'iSortingCols': '1',
        dt.populate_records()
        self.assertEqual(dt.get_ordering_splits(), (["-name"], []))
        self.assertEqual(list(dt._records), [obj1, obj2])

    def test_sort_uses_all_sources(self):
        from datetime import timedelta

        obj1 = ExampleModel.objects.create(name="a")
        obj2 = ExampleModel.objects.create(name="a")
        obj3 = ExampleModel.objects.create(name="b")
        obj1.date_created = (obj1.date_created + timedelta(days=3)).replace(
            tzinfo=datetime.timezone.utc
        )
        obj2.date_created = (obj2.date_created + timedelta(days=1)).replace(
            tzinfo=datetime.timezone.utc
        )
        obj3.date_created = (obj3.date_created + timedelta(days=2)).replace(
            tzinfo=datetime.timezone.utc
        )
        obj1.save()
        obj2.save()
        obj3.save()

        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            my_column = TextColumn("Data", sources=["name", "date_created", "pk"])

            class Meta:
                model = ExampleModel
                columns = ["my_column"]

        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "asc"}
        )  # 'iSortingCols': '1',
        dt.populate_records()
        self.assertEqual(dt.get_ordering_splits(), (["my_column"], []))
        self.assertEqual(list(dt._records), [obj2, obj1, obj3])

        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "desc"}
        )  # 'iSortingCols': '1',
        dt.populate_records()
        self.assertEqual(dt.get_ordering_splits(), (["-my_column"], []))
        self.assertEqual(list(dt._records), [obj3, obj1, obj2])

        # Swap the order of 'date_created' and 'name' fields in the sources, which will alter the
        # sort results.
        class DT(Datatable):
            my_column = TextColumn("Data", sources=["date_created", "name", "pk"])

            class Meta:
                model = ExampleModel
                columns = ["my_column"]

        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "asc"}
        )  # 'iSortingCols': '1',
        dt.populate_records()
        self.assertEqual(dt.get_ordering_splits(), (["my_column"], []))
        self.assertEqual(list(dt._records), [obj2, obj3, obj1])

        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "desc"}
        )  # 'iSortingCols': '1',
        dt.populate_records()
        self.assertEqual(dt.get_ordering_splits(), (["-my_column"], []))
        self.assertEqual(list(dt._records), [obj1, obj3, obj2])

    def test_sort_ignores_virtual_sources_when_mixed(self):
        from datetime import timedelta

        obj1 = ExampleModel.objects.create(name="a")
        obj2 = ExampleModel.objects.create(name="b")
        obj3 = ExampleModel.objects.create(name="a")

        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            my_column = TextColumn("Data", sources=["name", "get_absolute_url"])

            class Meta:
                model = ExampleModel
                columns = ["my_column"]

        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "asc"}
        )  # 'iSortingCols': '1',
        dt.populate_records()
        self.assertEqual(dt.get_ordering_splits(), (["my_column"], []))
        self.assertEqual(list(dt._records), [obj1, obj3, obj2])

        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "desc"}
        )  # 'iSortingCols': '1',
        dt.populate_records()
        self.assertEqual(dt.get_ordering_splits(), (["-my_column"], []))
        self.assertEqual(list(dt._records), [obj2, obj1, obj3])  # pk is natural ordering 1,3 here

        # Swap the sources order, but we expect the same result
        class DT(Datatable):
            my_column = TextColumn(
                "Data", sources=["get_absolute_url", "name"], processor="get_data"
            )

            class Meta:
                model = ExampleModel
                columns = ["my_column"]

            def get_data(self, obj, **kwargs):
                # Return data that would make the sort order wrong if it were consulted for sorting
                return obj.pk  # tracks with get_absolute_url

        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "asc"}
        )  # 'iSortingCols': '1',
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj1, obj3, obj2])

        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "desc"}
        )  # 'iSortingCols': '1',
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj2, obj1, obj3])  # pk is natural ordering 1,3 here

    def test_sort_uses_virtual_sources_when_no_db_sources_available(self):
        from datetime import timedelta

        obj1 = ExampleModel.objects.create(name="a")
        obj2 = ExampleModel.objects.create(name="b")
        obj3 = ExampleModel.objects.create(name="c")

        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            pk = TextColumn("Data", sources=["get_negative_pk"])

            class Meta:
                model = ExampleModel
                columns = ["pk"]

        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "asc"}
        )  # 'iSortingCols': '1',
        dt.populate_records()
        self.assertEqual(dt.get_ordering_splits(), ([], ["pk"]))
        self.assertEqual(list(dt._records), [obj3, obj2, obj1])

        dt = DT(
            queryset, "/", query_config={"order[0][column]": "0", "order[0][dir]": "desc"}
        )  # 'iSortingCols': '1',
        dt.populate_records()
        self.assertEqual(dt.get_ordering_splits(), ([], ["-pk"]))
        self.assertEqual(list(dt._records), [obj1, obj2, obj3])

    def test_get_object_pk(self):
        obj1 = ExampleModel.objects.create(name="test name 1")
        queryset = ExampleModel.objects.all()
        dt = Datatable(queryset, "/")
        self.assertEqual(dt.get_object_pk(obj1), obj1.pk)

    def test_get_extra_record_data_passes_through_to_object_serialization(self):
        obj1 = ExampleModel.objects.create(name="test name 1")
        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            def get_extra_record_data(self, obj):
                return {"custom": "data"}

        dt = DT([], "/")
        data = dt.get_record_data(obj1)
        self.assertIn("_extra_data", data)
        self.assertIn("custom", data["_extra_data"])
        self.assertEqual(data["_extra_data"]["custom"], "data")

    def test_get_extra_record_data_passes_through_to_json_response(self):
        obj1 = ExampleModel.objects.create(name="test name 1")
        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            def get_extra_record_data(self, obj):
                return {"custom": "data"}

        class FakeRequest(object):
            method = "GET"
            GET = {"sEcho": 0}

        dt = DT(queryset, "/")
        view = DatatableJSONResponseMixin()
        view.request = FakeRequest()
        data = view.get_json_response_object(dt)
        self.assertIn("data", data)
        self.assertIn("DT_RowData", data["data"][0])
        self.assertEqual(data["data"][0]["DT_RowData"], {"custom": "data"})

    def test_get_column_value_forwards_to_column_class(self):
        class CustomColumn1(Column):
            def value(self, obj, **kwargs):
                return "first"

        class CustomColumn2(Column):
            def value(self, obj, **kwargs):
                return "second"

        class DT(Datatable):
            fake1 = CustomColumn1("Fake1", sources=["get_absolute_url"])
            fake2 = CustomColumn2("Fake2", sources=["get_absolute_url"])

            class Meta:
                model = ExampleModel
                columns = ["name", "fake1", "fake2"]

        obj1 = ExampleModel.objects.create(name="test name 1")
        queryset = ExampleModel.objects.all()
        dt = DT(queryset, "/")
        data = dt.get_record_data(obj1)
        self.assertIn("1", data)
        self.assertIn(data["1"], "first")
        self.assertIn("2", data)
        self.assertIn(data["2"], "second")

    def test_get_processor_method(self):
        class Dummy(object):
            def fake_callback(self):
                pass

        view = Dummy()

        # Test no callback given
        dt = Datatable([], "/")
        f = dt.get_processor_method(Column("Fake", sources=["fake"]), i=0)
        self.assertEqual(f, None)

        class DT(Datatable):
            def fake_callback(self):
                pass

        column = Column("Fake", sources=["fake"], processor="fake_callback")

        # Test callback found on self
        dt = DT([], "/")
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, dt.fake_callback)

        # Test callback found on callback_target
        dt = Datatable([], "/", callback_target=view)
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, view.fake_callback)

    def test_get_processor_method_returns_direct_callable(self):
        def fake_callback():
            pass

        column = Column("Fake", sources=[], processor=fake_callback)

        # Test no callback given
        dt = Datatable([], "/")
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

        column = Column("Fake", sources=[])
        column.name = "fake"

        # Test implied named callback found first
        view = DummyNamed()
        dt = Datatable([], "/", callback_target=view)
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, view.get_column_fake_data)

        # Test implied named callback found first
        view = DummyIndexed()
        dt = Datatable([], "/", callback_target=view)
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, view.get_column_0_data)

        # Test implied named callback found first
        view = DummyBoth()
        dt = Datatable([], "/", callback_target=view)
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
        dt = DTNamed([], "/")
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, dt.get_column_fake_data)

        # Test implied named callback found first
        dt = DTIndexed([], "/")
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, dt.get_column_0_data)

        # Test implied named callback found first
        dt = DTBoth([], "/")
        f = dt.get_processor_method(column, i=0)
        self.assertEqual(f, dt.get_column_fake_data)

    def test_iter_datatable_yields_columns(self):
        class CustomColumn1(Column):
            pass

        class CustomColumn2(Column):
            pass

        class DT(Datatable):
            fake1 = CustomColumn1("Fake1", sources=["get_absolute_url"])
            fake2 = CustomColumn2("Fake2", sources=["get_absolute_url"])

            class Meta:
                model = ExampleModel
                columns = ["name", "fake1", "fake2"]

        dt = DT([], "/")
        self.assertEqual(isgenerator(dt.__iter__()), True)
        self.assertEqual(list(dt), [dt.columns["name"], dt.columns["fake1"], dt.columns["fake2"]])

    def test_search_term_basic(self):
        obj1 = ExampleModel.objects.create(name="test name 1")
        obj2 = ExampleModel.objects.create(name="test name 2")
        obj3 = ExampleModel.objects.create(name="test name 12")
        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            class Meta:
                model = ExampleModel
                columns = ["name"]

        dt = DT(queryset, "/", query_config={"search[value]": "test"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj1, obj2, obj3])

        dt = DT(queryset, "/", query_config={"search[value]": "name"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj1, obj2, obj3])

        dt = DT(queryset, "/", query_config={"search[value]": "1"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj1, obj3])

        dt = DT(queryset, "/", query_config={"search[value]": "2"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj2, obj3])

        dt = DT(queryset, "/", query_config={"search[value]": "12"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj3])

        dt = DT(queryset, "/", query_config={"search[value]": "3"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [])

    def test_search_term_boolean(self):
        obj1 = ExampleModel.objects.create(name="test name 1", value=True)
        obj2 = ExampleModel.objects.create(name="test name 2", value=True)
        obj3 = ExampleModel.objects.create(name="test name 12", value=False)
        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            senior = BooleanColumn("Senior:", "value")

            class Meta:
                model = ExampleModel
                columns = ["name", "senior"]

        dt = DT(queryset, "/", query_config={"search[value]": "True"})
        dt.populate_records()
        self.assertEqual(len(list(dt._records)), 2)

        dt = DT(queryset, "/", query_config={"search[value]": "false"})
        dt.populate_records()
        self.assertEqual(len(list(dt._records)), 1)

        dt = DT(queryset, "/", query_config={"search[value]": "SENIOR"})
        dt.populate_records()
        self.assertEqual(len(list(dt._records)), 2)

        dt = DT(queryset, "/", query_config={"search[value]": "menior"})
        dt.populate_records()
        self.assertEqual(len(list(dt._records)), 0)

    def test_search_multiple_terms_use_AND(self):
        obj1 = ExampleModel.objects.create(name="test name 1")
        obj2 = ExampleModel.objects.create(name="test name 2")
        obj3 = ExampleModel.objects.create(name="test name 12")
        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            class Meta:
                model = ExampleModel
                columns = ["name"]

        dt = DT(queryset, "/", query_config={"search[value]": "test name"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj1, obj2, obj3])

        dt = DT(queryset, "/", query_config={"search[value]": "test 1"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj1, obj3])

        dt = DT(queryset, "/", query_config={"search[value]": "test 2"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj2, obj3])

        dt = DT(queryset, "/", query_config={"search[value]": "test 12"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj3])

        dt = DT(queryset, "/", query_config={"search[value]": "test 3"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [])

    def test_search_term_queries_all_columns(self):
        r1 = RelatedModel.objects.create(name="test related 1 one")
        r2 = RelatedModel.objects.create(name="test related 2 two")
        obj1 = ExampleModel.objects.create(name="test name 1", related=r1)
        obj2 = ExampleModel.objects.create(name="test name 2", related=r2)

        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            related = TextColumn("Related", ["related__name"])

            class Meta:
                model = ExampleModel
                columns = ["name", "related"]

        dt = DT(queryset, "/", query_config={"search[value]": "test"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj1, obj2])

        dt = DT(queryset, "/", query_config={"search[value]": "test name"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj1, obj2])

        dt = DT(queryset, "/", query_config={"search[value]": "test 2"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj2])

        dt = DT(queryset, "/", query_config={"search[value]": "related 2"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj2])

        dt = DT(queryset, "/", query_config={"search[value]": "test one"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj1])

        dt = DT(queryset, "/", query_config={"search[value]": "2 two"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj2])

        dt = DT(queryset, "/", query_config={"search[value]": "test three"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [])

    def test_search_term_queries_extra_fields(self):
        r1 = RelatedModel.objects.create(name="test related 1 one")
        r2 = RelatedModel.objects.create(name="test related 2 two")
        obj1 = ExampleModel.objects.create(name="test name 1", related=r1)
        obj2 = ExampleModel.objects.create(name="test name 2", related=r2)

        queryset = ExampleModel.objects.all()

        class DT(Datatable):
            related = TextColumn("Related", ["related__name"])

            class Meta:
                model = ExampleModel
                columns = ["related"]
                search_fields = ["name"]

        dt = DT(queryset, "/", query_config={"search[value]": "test"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj1, obj2])

        dt = DT(queryset, "/", query_config={"search[value]": "test name 2"})
        dt.populate_records()
        self.assertEqual(list(dt._records), [obj2])


class ValuesDatatableTests(DatatableViewTestCase):
    def test_get_object_pk(self):
        obj1 = ExampleModel.objects.create(name="test name 1")
        queryset = ExampleModel.objects.all()
        dt = ValuesDatatable(queryset, "/")
        obj_data = queryset.values("pk")[0]
        self.assertEqual(dt.get_object_pk(obj_data), obj1.pk)
