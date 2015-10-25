# -*- encoding: utf-8 -*-
from .testcase import DatatableViewTestCase
from .test_app import models
from ..columns import Column, COLUMN_CLASSES
from ..exceptions import ColumnError
from .. import utils

class ColumnTests(DatatableViewTestCase):
    def test_custom_column_registers_itself(self):
        previous_length = len(COLUMN_CLASSES)

        class CustomColumn(Column):
            model_field_class = 'fake'

        self.assertEqual(len(COLUMN_CLASSES), previous_length + 1)
        self.assertEqual(COLUMN_CLASSES[0][0], CustomColumn)
        self.assertEqual(COLUMN_CLASSES[0][1], [CustomColumn.model_field_class] + CustomColumn.handles_field_classes)

        del COLUMN_CLASSES[:1]

    def test_value_is_pair(self):
        obj = models.ExampleModel.objects.create(name="test name 1")

        column = Column()
        value = column.value(obj)
        self.assertEqual(type(value), tuple)

    # def test_process_value_checks_all_sources(self):
    def test_process_value_is_empty_for_fake_source(self):
        processed = []

        def processor(value, **kwargs):
            processed.append(value)

        obj = models.ExampleModel.objects.create(name="test name 1")

        # Verify bad source names don't find values
        processed[:] = []
        column = Column(sources=['fake1'], processor=processor)
        column.value(obj)
        self.assertEqual(processed, [])

        column = Column(sources=['fake1', 'fake2'], processor=processor)
        column.value(obj)
        self.assertEqual(processed, [])
