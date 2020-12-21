# -*- coding: utf-8 -*-
"""setup.py: Django django-datatables-view"""

from setuptools import setup, find_packages

with open('README.md') as f:
    long_description = f.read()

setup(name='django-datatable-view',
      version='1.0.0',
      description='This package is used in conjunction with the jQuery plugin '
                  '(http://http://datatables.net/), and supports state-saving detection'
                  ' with (http://datatables.net/plug-ins/api).  The package consists of '
                  'a class-based view, and a small collection of utilities for rendering'
                  ' table data from models.',
      long_description=long_description,
      long_description_content_type='text/markdown',
      author='Autumn Valenta',
      author_email='avalenta@pivotalenergysolutions.com',
      url='https://github.com/pivotal-energy-solutions/django-datatable-view',
      # download_url='https://github.com/pivotal-energy-solutions/django-datatable-view/tarball/django-datatable-view-0.9.0',
      license='Apache License (2.0)',
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Web Environment',
          'Framework :: Django',
          'Framework :: Django :: 2.1',
          'Framework :: Django :: 2.2',
          'Framework :: Django :: 3.1',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: Apache Software License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3',
          'Topic :: Software Development',
      ],
      packages=find_packages(),
      package_data={'datatableview': ['static/js/*.js', 'templates/datatableview/*.html']},
      include_package_data=True,
      install_requires=['django>=2.1', 'python-dateutil'],
      )
