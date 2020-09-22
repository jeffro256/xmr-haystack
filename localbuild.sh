PIPNAME=xmr-haystack-jeffro256

rm -r build/ dist/
python setup.py sdist bdist_wheel
pip3 uninstall $PIPNAME
pip3 install dist/*.whl

