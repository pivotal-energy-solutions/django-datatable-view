# -*- encoding: utf-8 -*-

import json
import logging

from ..forms import SelectizeUpdateForm
from .base import DatatableView

from django import get_version
from django.http import HttpResponse
from django.views.generic.edit import FormView

log = logging.getLogger(__name__)

CAN_UPDATE_FIELDS = get_version().split('.') >= ['1', '5']


class SelectizeMixin(FormView):
    form_class = SelectizeUpdateForm
    
    def get_context_data(self, *args, **kwargs):
        data = super(SelectizeMixin, self).get_context_data(*args, **kwargs)
        data['form'] = self.form_class();
        return data
    def post(self, request, *args, **kwargs):
        """
        Builds a dynamic form that targets only the field in question, and saves the modification.
        """
        self.object_list = None
        form = self.get_selectize_form()
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

    def get_selectize_form_kwargs(self):
        """ Returns a dict of keyword arguments to be sent to the selectize form class. """
        kwargs = {
            'model': self.get_queryset().model,
        }
        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.request.POST,
            })
        return kwargs

    def get_selectize_form(self):
        """ Builds selectize form with get_selectize_form_kwargs args """
        print "hello"
        return self.form_class(**self.get_selectize_form_kwargs())

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


class SelectizeDatatableView(SelectizeMixin, DatatableView):
    pass
