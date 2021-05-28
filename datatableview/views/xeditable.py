# -*- coding: utf-8 -*-

import json
import logging

from ..forms import XEditableUpdateForm
from .base import DatatableView

from django import get_version
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import ForeignKey

log = logging.getLogger(__name__)

CAN_UPDATE_FIELDS = get_version().split(".") >= ["1", "5"]


class XEditableMixin(object):
    xeditable_form_class = XEditableUpdateForm

    xeditable_fieldname_param = "xeditable_field"  # GET parameter name used for choices ajax

    @method_decorator(ensure_csrf_cookie)
    def dispatch(self, request, *args, **kwargs):
        """Introduces the ``ensure_csrf_cookie`` decorator and handles xeditable choices ajax."""
        if request.GET.get(self.xeditable_fieldname_param):
            return self.get_ajax_xeditable_choices(request, *args, **kwargs)
        return super(XEditableMixin, self).dispatch(request, *args, **kwargs)

    def get_ajax_xeditable_choices(self, request, *args, **kwargs):
        """AJAX GET handler for xeditable queries asking for field choice lists."""
        field_name = request.GET.get(self.xeditable_fieldname_param)
        if not field_name:
            return HttpResponseBadRequest("Field name must be given")

        queryset = self.get_queryset()
        if not self.model:
            self.model = queryset.model

        # Sanitize the requested field name by limiting valid names to the datatable_options columns
        from datatableview.views import legacy

        if isinstance(self, legacy.LegacyDatatableMixin):
            columns = self._get_datatable_options()["columns"]
            for name in columns:
                if isinstance(name, (list, tuple)):
                    name = name[1]
                if name == field_name:
                    break
            else:
                return HttpResponseBadRequest("Invalid field name")
        else:
            datatable = self.get_datatable()
            if not hasattr(datatable, "config"):
                datatable.configure()
            if field_name not in datatable.config["columns"]:
                return HttpResponseBadRequest("Invalid field name")

        field = self.model._meta.get_field(field_name)
        choices = self.get_field_choices(field, field_name)
        return HttpResponse(json.dumps(choices))

    def post(self, request, *args, **kwargs):
        """
        Builds a dynamic form that targets only the field in question, and saves the modification.
        """
        self.object_list = None
        form = self.get_xeditable_form(self.get_xeditable_form_class())
        if form.is_valid():
            obj = self.get_update_object(form)
            if obj is None:
                data = json.dumps({"status": "error", "message": "Object does not exist."})
                return HttpResponse(data, content_type="application/json", status=404)
            return self.update_object(form, obj)
        else:
            data = json.dumps(
                {
                    "status": "error",
                    "message": "Invalid request",
                    "form_errors": form.errors,
                }
            )
            return HttpResponse(data, content_type="application/json", status=400)

    def get_xeditable_form_class(self):
        """Returns ``self.xeditable_form_class``."""
        return self.xeditable_form_class

    def get_xeditable_form_kwargs(self):
        """Returns a dict of keyword arguments to be sent to the xeditable form class."""
        kwargs = {
            "model": self.get_queryset().model,
        }
        if self.request.method in ("POST", "PUT"):
            kwargs.update(
                {
                    "data": self.request.POST,
                }
            )
        return kwargs

    def get_xeditable_form(self, form_class):
        """Builds xeditable form computed from :py:meth:`.get_xeditable_form_class`."""
        return form_class(**self.get_xeditable_form_kwargs())

    def get_update_object(self, form):
        """
        Retrieves the target object based on the update form's ``pk`` and the table's queryset.
        """
        pk = form.cleaned_data["pk"]
        queryset = self.get_queryset()
        try:
            obj = queryset.get(pk=pk)
        except queryset.model.DoesNotExist:
            obj = None

        return obj

    def update_object(self, form, obj):
        """Saves the new value to the target object."""
        field_name = form.cleaned_data["name"]
        value = form.cleaned_data["value"]

        for validator in obj._meta.get_field(field_name).validators:
            try:
                validator(value)
            except ValidationError as e:
                data = json.dumps(
                    {
                        "status": "error",
                        "message": "Invalid request",
                        "form_errors": {field_name: [e.message]},
                    }
                )
                return HttpResponse(data, content_type="application/json", status=400)

        setattr(obj, field_name, value)
        save_kwargs = {}
        if CAN_UPDATE_FIELDS:
            save_kwargs["update_fields"] = [field_name]
        obj.save(**save_kwargs)

        data = json.dumps(
            {
                "status": "success",
            }
        )
        return HttpResponse(data, content_type="application/json")

    def get_field_choices(self, field, field_name):
        """
        Returns the valid choices for ``field``.  The ``field_name`` argument is given for
        convenience.
        """
        if self.request.GET.get("select2"):
            names = ["id", "text"]
        else:
            names = ["value", "text"]
        choices_getter = getattr(self, "get_field_%s_choices", None)
        if choices_getter is None:
            if isinstance(field, ForeignKey):
                choices_getter = self._get_foreignkey_choices
            else:
                choices_getter = self._get_default_choices
        return [dict(zip(names, choice)) for choice in choices_getter(field, field_name)]

    def _get_foreignkey_choices(self, field, field_name):
        formfield_kwargs = {}
        if not field.blank:
            # Explicitly remove empty choice, since formfield isn't working with instance data and
            # will consequently try to assume initial=None, forcing the blank option to appear.
            formfield_kwargs["empty_label"] = None
        formfield = field.formfield(**formfield_kwargs)
        return formfield.choices

    def _get_default_choices(self, field, field_name):
        return field.choices


class XEditableDatatableView(XEditableMixin, DatatableView):
    pass
