from django.db import models

class ExampleModel(models.Model):
    name = models.CharField(max_length=15)
    date_created = models.DateTimeField(auto_now_add=True)
    related = models.ForeignKey('RelatedModel', blank=True, null=True)
    relateds = models.ManyToManyField('RelatedM2MModel', blank=True)

class RelatedModel(models.Model):
    name = models.CharField(max_length=15)

class RelatedM2MModel(models.Model):
    name = models.CharField(max_length=15)

class ReverseRelatedModel(models.Model):
    name = models.CharField(max_length=15)
    example = models.ForeignKey('ExampleModel')
