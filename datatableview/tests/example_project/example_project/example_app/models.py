# -*- encoding: utf-8 -*-

from django.db import models

class Blog(models.Model):
    name = models.CharField(max_length=100)
    tagline = models.TextField()

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return "#blog-{pk}".format(pk=self.pk)


class Author(models.Model):
    name = models.CharField(max_length=50)
    email = models.EmailField()

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return "#author-{pk}".format(pk=self.pk)


class Entry(models.Model):

    _rating_choices = (
        (0, 'Ridiculous'),
        (1, 'Awful'),
        (2, 'Bad'),
        (3, 'Average'),
        (4, 'Good'),
        (5, 'Excellent'),
    )

    blog = models.ForeignKey(Blog)
    headline = models.CharField(max_length=255)
    body_text = models.TextField()
    pub_date = models.DateField()
    mod_date = models.DateField()
    authors = models.ManyToManyField(Author)
    n_comments = models.IntegerField()
    n_pingbacks = models.IntegerField()
    rating = models.IntegerField(choices=_rating_choices)

    def __unicode__(self):
        return self.headline

    def get_absolute_url(self):
        return "#entry-{pk}".format(pk=self.pk)

    def get_pub_date(self):
        return self.pub_date

    def get_interaction_total(self):
        return self.n_comments + self.n_pingbacks
