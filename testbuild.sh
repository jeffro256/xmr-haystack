PIPNAME=xmr-haystack
rm -r build/ dist/
python3 setup.py sdist bdist_wheel
python3 -m twine upload --repository testpypi dist/*
pip3 uninstall $PIPNAME
pip3 install --index-url https://test.pypi.org/simple --no-deps $PIPNAME

