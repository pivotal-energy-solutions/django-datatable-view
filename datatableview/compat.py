# -*- encoding: utf-8 -*-
""" Backports of code left behind by new versions of Django. """

import six


# Django 1.7 removed StrAndUnicode, so it has been purged from this project as well.  To bridge the
# gap, we will rely on this utility directly, instead of trying to generate our own replacement
# StrAndUnicode class.
def python_2_unicode_compatible(klass):
    """
    A decorator that defines __unicode__ and __str__ methods under Python 2.
    Under Python 3 it does nothing.

    To support Python 2 and 3 with a single code base, define a __str__ method
    returning text and apply this decorator to the class.
    """
    if not six.PY3:
        klass.__unicode__ = klass.__str__
        klass.__str__ = lambda self: self.__unicode__().encode('utf-8')
    return klass
