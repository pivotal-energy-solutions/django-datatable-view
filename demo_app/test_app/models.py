# -*- coding: utf-8 -*-

from django.db import models


class ExampleModel(models.Model):
    name = models.CharField(max_length=64)
    value = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    related = models.ForeignKey("RelatedModel", blank=True, null=True, on_delete=models.CASCADE)
    relateds = models.ManyToManyField("RelatedM2MModel", blank=True)

    def __str__(self):
        return "ExampleModel %d" % (self.pk,)

    def __repr__(self):
        return "<ExampleModel: %d:'%s'>" % (
            self.pk,
            self.name,
        )

    def get_absolute_url(self):
        return "#{pk}".format(pk=self.pk)

    def get_negative_pk(self):
        return -1 * self.pk


class RelatedModel(models.Model):
    name = models.CharField(max_length=64)

    def __str__(self):
        return "RelatedModel %d" % (self.pk,)

    def get_absolute_url(self):
        return "#{pk}".format(pk=self.pk)


class RelatedM2MModel(models.Model):
    name = models.CharField(max_length=15)


class ReverseRelatedModel(models.Model):
    name = models.CharField(max_length=15)
    example = models.ForeignKey("ExampleModel", on_delete=models.CASCADE)
