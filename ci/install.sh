#! /bin/bash

PYTHON_VERSION=$(python --version 2>&1)

if [[ "$PYTHON_VERSION" > "Python 3" ]]
then
  if [[ "$DJANGO" < "Django==1.5" ]]
  then
    echo "Cannot install $DJANGO on $PYTHON_VERSION"
    exit
  fi
fi

pip install -q Django==$DJANGO --use-mirrors
pip install pep8 --use-mirrors
pip install pyflakes
pip install -q -e . --use-mirrors
