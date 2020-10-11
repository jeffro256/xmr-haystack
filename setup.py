from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / 'README.md').read_text(encoding='utf-8')

setup(
    name='xmr-haystack',
    version='0.0.3',
    description='Manage your on-chain Monero privacy with xmr-haystack',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/jeffreo256/xmr-haystack',
    author='Jeffrey Ryan',
    author_email='jeffaryan7@gmail.com',
    # For a list of valid classifiers, see https://pypi.org/classifiers/
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate you support Python 3. These classifiers are *not*
        # checked by 'pip install'. See instead 'python_requires' below.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3 :: Only',
    ],
    keywords='monero, blockchain, wallet, privacy, finance',
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    python_requires='>=3.5, <4',
    install_requires=['cryptography', 'requests', 'bidict'],
    #extras_require={  # Optional
    #    'dev': ['check-manifest'],
    #    'test': ['coverage'],
    #},
    #package_data={  # Optional
    #    'sample': ['package_data.dat'],
    #},
    #data_files=[('my_data', ['data/data_file'])],  # Optional
    #entry_points={  # Optional
    #    'console_scripts': [
    #        'sample=sample:main',
    #    ],
    #},
    project_urls={  # Optional
        'Bug Reports': 'https://github.com/jeffro256/xmr-haystack/issues',
        'Funding': 'https://github.com/jeffro256/xmr-haystack',
        'Source': 'https://github.com/jeffro256/xmr-haystack',
    }
)
