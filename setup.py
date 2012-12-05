# -*- coding: utf-8 -*-
"""setup.py: Django django-datatables-view"""

from distutils.core import setup

setup(name='django-datatable-view',
      version='1.0',
      description='This package is used in conjunction with the jQuery plugin '
                  '(http://http://datatables.net/), and supports state-saving detection'
                  ' with (http://datatables.net/plug-ins/api).  The package consists of '
                  'a class-based view, and a small collection of utilities for '
                  'internal and external use.',
      author='Tim Vallenta',
      author_email='tvalenta@pivotalenergysolutions.com',
      url='https://github.com/pivotal-energy-solutions/django-datatable-view',
      license='lgpl',
      classifiers=[
           'Development Status :: 2 - Pre-Alpha',
           'Environment :: Web Environment',
           'Framework :: Django',
           'Intended Audience :: Developers',
           'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
           'Operating System :: OS Independent',
           'Programming Language :: Python',
           'Topic :: Software Development',
      ],
      packages=['datatableview'],
      requires=['django (>=1.2)',],
)
