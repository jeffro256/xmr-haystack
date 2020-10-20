#!/bin/bash
FILE1="dist/$(ls -t dist | head -n2 | head -n1)"
FILE2="dist/$(ls -t dist | head -n2 | tail -n1)"
python setup.py sdist bdist_wheel
python -m twine upload --repository testpypi "$FILE1" "$FILE2"
