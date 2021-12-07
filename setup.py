# -*- coding: utf-8 -*-
"""setup.py: Django django-datatables-view"""

__name__ = "datatableview"
__author__ = "Autumn Valenta"
__version_info__ = (2, 1, 9)
__version__ = "2.1.9"
__date__ = "2013/11/14 2:00:00 PM"
__credits__ = ["Autumn Valenta", "Steven Klass"]
__license__ = "See the file LICENSE.txt for licensing information."


from setuptools import setup, find_packages

with open("README.md") as f:
    long_description = f.read()

setup(
    name="django-datatable-view",
    version="2.1.9",
    description="This package is used in conjunction with the jQuery plugin "
    "(http://http://datatables.net/), and supports state-saving detection"
    " with (http://datatables.net/plug-ins/api).  The package consists of "
    "a class-based view, and a small collection of utilities for rendering"
    " table data from models.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Autumn Valenta",
    author_email="avalenta@pivotalenergysolutions.com",
    url="https://github.com/pivotal-energy-solutions/django-datatable-view",
    license="Apache License (2.0)",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.0",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development",
    ],
    python_requires=">=3.9.*",
    install_requires=["django>=3.2", "python-dateutil"],
    packages=find_packages(),
    package_data={"datatableview": ["static/js/*.js", "templates/datatableview/*.html"]},
    include_package_data=True,
)
