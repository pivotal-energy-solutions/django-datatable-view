# -*- coding: utf-8 -*-
"""setup.py: Django django-datatables-view"""

from setuptools import setup, find_packages

setup(name='django-datatable-view',
      version='0.5.0',
      description='This package is used in conjunction with the jQuery plugin '
                  '(http://http://datatables.net/), and supports state-saving detection'
                  ' with (http://datatables.net/plug-ins/api).  The package consists of '
                  'a class-based view, and a small collection of utilities for rendering'
                  ' table data from models.',
      author='Tim Valenta',
      author_email='tvalenta@pivotalenergysolutions.com',
      url='https://github.com/pivotal-energy-solutions/django-datatable-view',
      license='Apache License (2.0)',
      classifiers=[
           'Development Status :: 2 - Pre-Alpha',
           'Environment :: Web Environment',
           'Framework :: Django',
           'Intended Audience :: Developers',
           'License :: OSI Approved :: Apache Software License',
           'Operating System :: OS Independent',
           'Programming Language :: Python',
           'Topic :: Software Development',
      ],
      packages=find_packages(exclude=['tests', 'tests.*']),
      package_data={'datatableview': ['static/js/*.js', 'templates/datatableview/*.html']},
      include_package_data=True,
      requires=['django (>=1.2)'],
)
