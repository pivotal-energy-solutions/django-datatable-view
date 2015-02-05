import json
import re
import operator
import logging

from ..forms import XEditableUpdateForm
from .base import DatatableView

from django import get_version
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import ensure_csrf_cookie

log = logging.getLogger(__name__)

CAN_UPDATE_FIELDS = get_version().split('.') >= ['1', '5']

class XEditableMixin(object):
    xeditable_form_class = XEditableUpdateForm

    xeditable_fieldname_param = 'xeditable_field'  # GET parameter name used for choices ajax

    def get(self, request, *args, **kwargs):
        """ Introduces the ``ensure_csrf_cookie`` decorator and handles xeditable choices ajax. """
        if request.GET.get(self.xeditable_fieldname_param):
            return self.get_ajax_xeditable_choices(request, *args, **kwargs)

        # Doing this in the method body at runtime instead of at declaration-time helps prevent
        # collisions of other subclasses also trying to decorate their own get() methods.
        method = super(XEditableMixin, self).get
        method = ensure_csrf_cookie(method)
        return method(request, *args, **kwargs)

    def get_ajax_xeditable_choices(self, request, *args, **kwargs):
        """ AJAX GET handler for xeditable queries asking for field choice lists. """
        field_name = request.GET[self.xeditable_fieldname_param]

        queryset = self.get_queryset()
        if not self.model:
            self.model = queryset.model

        # Sanitize the requested field name by limiting valid names to the datatable_options columns
        columns = self._get_datatable_options()['columns']
        for name in columns:
            if isinstance(name, (list, tuple)):
                name = name[1]
            if name == field_name:
                break
        else:
            return HttpResponseBadRequest()

        field = self.model._meta.get_field_by_name(field_name)[0]

        choices = self.get_field_choices(field, field_name)
        return HttpResponse(json.dumps(choices))

    def post(self, request, *args, **kwargs):
        self.object_list = None
        form = self.get_xeditable_form(self.get_xeditable_form_class())
        if form.is_valid():
            obj = self.get_update_object(form)
            if obj is None:
                data = json.dumps({
                    'status': 'error',
                    'message': "Object does not exist."
                })
                return HttpResponse(data, content_type="application/json", status=404)
            return self.update_object(form, obj)
        else:
            data = json.dumps({
                'status': 'error',
                'message': "Invalid request",
                'form_errors': form.errors,
            })
            return HttpResponse(data, content_type="application/json", status=400)

    def get_xeditable_form_class(self):
        return self.xeditable_form_class

    def get_xeditable_form_kwargs(self):
        kwargs = {
            'model': self.get_queryset().model,
        }
        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.request.POST,
            })
        return kwargs

    def get_xeditable_form(self, form_class):
        return form_class(**self.get_xeditable_form_kwargs())

    def get_update_object(self, form):
        """
        Retrieves the target object based on the update form's ``pk`` and the table's queryset.
        """
        pk = form.cleaned_data['pk']
        queryset = self.get_queryset()
        try:
            obj = queryset.get(pk=pk)
        except queryset.model.DoesNotExist:
            obj = None

        return obj

    def update_object(self, form, obj):
        """ Saves the new value to the target object. """
        field_name = form.cleaned_data['name']
        value = form.cleaned_data['value']
        setattr(obj, field_name, value)
        save_kwargs = {}
        if CAN_UPDATE_FIELDS:
            save_kwargs['update_fields'] = [field_name]
        obj.save(**save_kwargs)

        data = json.dumps({
            'status': 'success',
        })
        return HttpResponse(data, content_type="application/json")

    def get_field_choices(self, field, field_name):
        """ Returns the valid choices for ``field``.  ``field_name`` is given for convenience. """
        if self.request.GET.get('select2'):
            names = ['id', 'text']
        else:
            names = ['value', 'text']
        return [dict(zip(names, choice)) for choice in field.choices]


class XEditableDatatableView(XEditableMixin, DatatableView):
    pass
