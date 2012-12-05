# -*- coding: utf-8 -*-
"""setup.py: Django django-datatables-view"""

from distutils.core import setup
import os


def fullsplit(path, result=None):
    """
    Split a pathname into components (the opposite of os.path.join) in a
    platform-neutral way.
    """
    if result is None:
        result = []
    head, tail = os.path.split(path)
    if head == '':
        return [tail] + result
    if head == path:
        return result
    return fullsplit(head, [tail] + result)

# Compile the list of packages available, because distutils doesn't have
# an easy way to do this.
packages, data_files = [], []
root_dir = os.path.dirname(__file__)
if root_dir != '':
    os.chdir(root_dir)
_dir = 'datatableview'

for dirpath, dirnames, filenames in os.walk(_dir):
    # Ignore PEP 3147 cache dirs and those whose names start with '.'
    for i, dirname in enumerate(dirnames):
        if dirname.startswith('.') or dirname == '__pycache__':
            del dirnames[i]
    if '__init__.py' in filenames:
        packages.append('.'.join(fullsplit(dirpath)))
    elif filenames:
        # strip 'simple_history/' or 'simple_history\'
        prefix = dirpath[len(_dir) + 1:]
        for f in filenames:
            data_files.append(os.path.join(prefix, f))

        data_files.append([dirpath, [os.path.join(dirpath, f) for f in filenames]])

print data_files
print packages

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
      packages=packages,
      data_files=data_files,
      requires=['django (>=1.2)',],
)
