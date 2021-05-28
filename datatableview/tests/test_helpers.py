# -*- coding: utf-8 -*-

from datetime import datetime
from functools import partial

import django
from django.apps import apps

from datatableview import helpers

from .testcase import DatatableViewTestCase

ExampleModel = apps.get_model("test_app", "ExampleModel")
RelatedModel = apps.get_model("test_app", "RelatedModel")
RelatedM2MModel = apps.get_model("test_app", "RelatedM2MModel")

test_data_fixture = "test_data.json"


class HelpersTests(DatatableViewTestCase):
    fixtures = [test_data_fixture]

    def test_link_to_model(self):
        """Verifies that link_to_model works."""
        helper = helpers.link_to_model

        # Verify that a model without get_absolute_url() raises a complaint
        related = RelatedM2MModel.objects.get(pk=1)
        with self.assertRaises(AttributeError) as cm:
            helper(related)
        self.assertEqual(
            str(cm.exception), "'RelatedM2MModel' object has no attribute 'get_absolute_url'"
        )

        instance = ExampleModel.objects.get(pk=1)
        # Verify simple use
        output = helper(instance)
        self.assertEqual(output, '<a href="#1">ExampleModel 1</a>')

        # Verify text override
        output = helper(instance, text="Special text")
        self.assertEqual(output, '<a href="#1">Special text</a>')

        instance = ExampleModel.objects.get(pk=2)
        # Verify ``key`` access to transition an instance to a related field
        secondary_helper = helper(key=lambda o: o.related)
        output = secondary_helper(instance)
        self.assertEqual(output, '<a href="#1">RelatedModel 1</a>')

        # Verify ``key`` access version of custom text
        output = secondary_helper(instance, text="Special text")
        self.assertEqual(output, '<a href="#1">Special text</a>')

        # Verify ``attr`` as 'self' is the identity mapping
        secondary_helper = helper(attr="self")
        output = secondary_helper(instance)
        self.assertEqual(output, '<a href="#2">ExampleModel 2</a>')

        # Verify ``attr`` as a getattr shorthand lookup
        secondary_helper = helper(attr="related")
        output = secondary_helper(instance)
        self.assertEqual(output, '<a href="#1">RelatedModel 1</a>')

    def test_make_boolean_checkmark(self):
        """Verifies that make_boolean_checkmark works."""
        helper = helpers.make_boolean_checkmark

        # Verify simple use
        output = helper("True-ish value")
        self.assertEqual(output, "&#10004;")
        output = helper("")
        self.assertEqual(output, "&#10008;")

        # Verify custom values
        output = helper("True-ish value", true_value="Yes", false_value="No")
        self.assertEqual(output, "Yes")
        output = helper("", true_value="Yes", false_value="No")
        self.assertEqual(output, "No")

    def test_format_date(self):
        """Verifies that format_date works."""
        helper = helpers.format_date

        # Verify simple use
        data = datetime.now()
        secondary_helper = helper("%m/%d/%Y")
        output = secondary_helper(data)
        self.assertEqual(output, data.strftime("%m/%d/%Y"))

        # Verify that None objects get swallowed without complaint.
        # This helps promise that the helper won't blow up for models.DateTimeField that are allowed
        # to be null.
        output = secondary_helper(None)
        self.assertEqual(output, "")

    def test_format(self):
        """Verifies that format works."""
        helper = helpers.format

        # Verify simple use
        data = 1234567890
        secondary_helper = helper("{0:,}")
        output = secondary_helper(data)
        self.assertEqual(output, "{0:,}".format(data))

        # Verify ``cast`` argument
        data = "1234.56789"
        secondary_helper = helper("{0:.2f}", cast=float)
        output = secondary_helper(data)
        self.assertEqual(output, "{0:.2f}".format(float(data)))

    def test_through_filter(self):
        """Verifies that through_filter works."""
        helper = helpers.through_filter

        target_function = lambda data, arg=None: (data, arg)

        # Verify simple use
        data = "Data string"
        secondary_helper = helper(target_function)
        output = secondary_helper(data)
        self.assertEqual(output, (data, None))

        # Verify ``arg`` argument
        secondary_helper = helper(target_function, arg="Arg data")
        output = secondary_helper(data)
        self.assertEqual(output, (data, "Arg data"))

    def test_itemgetter(self):
        """Verifies that itemgetter works."""
        helper = helpers.itemgetter

        # Verify simple index access
        data = list(range(5))
        secondary_helper = helper(-1)
        output = secondary_helper(data)
        self.assertEqual(output, data[-1])

        # Verify slicing access
        secondary_helper = helper(slice(1, 3))
        output = secondary_helper(data)
        self.assertEqual(output, data[1:3])

        # Verify ellipsis works for strings
        data = str(range(10))
        secondary_helper = helper(slice(0, 5), ellipsis=True)
        output = secondary_helper(data)
        self.assertEqual(output, data[:5] + "...")

        # Verify ellipsis can be customized
        secondary_helper = helper(slice(0, 5), ellipsis="custom")
        output = secondary_helper(data)
        self.assertEqual(output, data[:5] + "custom")

        # Verify ellipsis does nothing for non-string data types
        data = range(10)
        output = secondary_helper(data)
        self.assertEqual(output, data[:5])

    def test_attrgetter(self):
        """Verifies that attrgetter works."""
        helper = helpers.attrgetter

        # Verify simple attr lookup
        data = ExampleModel.objects.get(pk=1)
        secondary_helper = helper("pk")
        output = secondary_helper(data)
        self.assertEqual(output, data.pk)

        # Verify bad attribrute lookup
        data = ExampleModel.objects.get(pk=1)
        secondary_helper = helper("bad field name")
        with self.assertRaises(AttributeError) as cm:
            output = secondary_helper(data)
        self.assertEqual(
            str(cm.exception), "'ExampleModel' object has no attribute 'bad field name'"
        )

    def test_make_xeditable(self):
        """Verifies that make_xeditable works."""
        helper = helpers.make_xeditable

        # Items that the helper normally expects in a callback context
        internals = {"field_name": "name"}

        # Verify chain calls don't trigger rendering
        secondary_helper = helper()
        tertiary_helper = secondary_helper()
        self.assertEqual(type(secondary_helper), partial)
        self.assertEqual(type(tertiary_helper), partial)

        # Verify chain ends with provision of a value
        data = ExampleModel.objects.get(pk=1)
        # This needs a "url" arg because we want to test successful use
        output = tertiary_helper(data, url="/", **internals)
        self.assertTrue(isinstance(output, str))

        # Verify that no "view" kwarg means the url is required from the call
        with self.assertRaises(ValueError) as cm:
            tertiary_helper(data, **internals)
        self.assertEqual(str(cm.exception), "'make_xeditable' cannot determine a value for 'url'.")

        # Verify kwargs accumulate
        kwargs1 = {"type": "textarea"}
        kwargs2 = {"other_arg": True}
        secondary_helper = helper(**kwargs1)
        expected_kwargs = dict(kwargs1, extra_attrs=[])
        self.assertEqual(secondary_helper.keywords, expected_kwargs)
        tertiary_helper = secondary_helper(**kwargs2)
        expected_kwargs = dict(kwargs1, **dict(kwargs2, extra_attrs=[]))
        self.assertEqual(tertiary_helper.keywords, expected_kwargs)

        # Verify default kwarg names end up as attributes
        data = ExampleModel.objects.get(pk=1)
        kwargs = {
            "pk": "PK DATA",
            "type": "TYPE DATA",
            "url": "URL DATA",
            "source": "SOURCE DATA",
            "title": "TITLE DATA",
            "placeholder": "PLACEHOLDER DATA",
            # Extra stuff not in anticipated to appear in rendered string
            "special": "SPECIAL DATA",
            "data_custom": "DATA-CUSTOM DATA",
        }
        secondary_helper = helper(**kwargs)
        output = secondary_helper(data, **internals)
        expected_output = """
        <a href="#" data-name="name"
                    data-pk="PK DATA"
                    data-placeholder="PLACEHOLDER DATA"
                    data-source="SOURCE DATA"
                    data-title="TITLE DATA"
                    data-type="TYPE DATA"
                    data-url="URL DATA"
                    data-value="1"
                    data-xeditable="xeditable">
            ExampleModel 1
        </a>
        """
        self.assertHTMLEqual(output, expected_output)

        # Verify that explicit additions via ``extra_attrs`` allows kwargs to appear in HTML as
        # "data-*" attributes.
        secondary_helper = helper(extra_attrs=["special", "data_custom", "fake"], **kwargs)
        output = secondary_helper(data, **internals)
        expected_output = """
        <a href="#" data-name="name"
                    data-pk="PK DATA"
                    data-placeholder="PLACEHOLDER DATA"
                    data-source="SOURCE DATA"
                    data-title="TITLE DATA"
                    data-type="TYPE DATA"
                    data-url="URL DATA"
                    data-value="1"
                    data-special="SPECIAL DATA"
                    data-custom="DATA-CUSTOM DATA"
                    data-xeditable="xeditable">
            ExampleModel 1
        </a>
        """
        self.assertHTMLEqual(output, expected_output)
