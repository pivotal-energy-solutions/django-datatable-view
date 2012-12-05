# -*- coding: utf-8 -*-
"""setup.py: Django django-datatables-view"""

from distutils.core import setup
import os

# compile the list of packages available, because distutils doesn't have an easy way to do this
packages, data_files = [], []
root_dir = os.path.dirname(__file__)
if root_dir:
    os.chdir(root_dir)

for dirpath, dirnames, filenames in os.walk('simple_history'):
    # ignore dirnames that start with '.'
    for i, dirname in enumerate(dirnames):
        if dirname.startswith('.'):
            del dirnames[i]
    if '__init__.py' in filenames:
        pkg = dirpath.replace(os.path.sep, '.')
        if os.path.altsep:
            pkg = pgk.replace(os.path.altsep, '.')
        packages.append(pkg)
    elif filenames:
        # strip 'simple_history/' or 'simple_history\'
        prefix = dirpath[15:]
        for f in filenames:
            data_files.append(os.path.join(prefix, f))

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
      package_dir={'datatableview': 'datatableview'},
      packages=packages,
      package_data={'datatableview': data_files},
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
)
