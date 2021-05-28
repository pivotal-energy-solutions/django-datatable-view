# -*- coding: utf-8 -*-

from django import forms
from django.forms import ValidationError
from django.forms.models import fields_for_model


class XEditableUpdateForm(forms.Form):
    """
    Represents only a single field of a given model instance.
    """

    # Note that a primary key can be anything at all, not just an integer
    pk = forms.CharField(max_length=512)

    # The field name we're editing on the target.
    # This isn't normally a great way to track the field name in the request, but we're going need
    # to validate the field against the model, so we use the form logic process to force the form
    # into failure mode if the field name is bad.
    # Displaying field itself should not be required on the frontend, but x-editable.js sends it
    # along as part of the editing widget.
    name = forms.CharField(max_length=100)

    def __init__(self, model, data, *args, **kwargs):
        super(XEditableUpdateForm, self).__init__(data, *args, **kwargs)

        self.model = model
        self.set_value_field(model, data.get("name"))

    def set_value_field(self, model, field_name):
        """
        Adds a ``value`` field to this form that uses the appropriate formfield for the named target
        field.  This will help to ensure that the value is correctly validated.
        """
        fields = fields_for_model(model, fields=[field_name])
        self.fields["value"] = fields[field_name]

    def clean_name(self):
        """Validates that the ``name`` field corresponds to a field on the model."""
        field_name = self.cleaned_data["name"]
        # get_all_field_names is deprecated in Django 1.8, this also fixes proxied models
        if hasattr(self.model._meta, "get_fields"):
            field_names = [field.name for field in self.model._meta.get_fields()]
        else:
            field_names = self.model._meta.get_all_field_names()
        if field_name not in field_names:
            raise ValidationError("%r is not a valid field." % field_name)
        return field_name
