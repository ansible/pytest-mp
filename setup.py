#!/usr/bin/env python
import os
import codecs
from setuptools import setup


version = '0.0.1'


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return codecs.open(file_path, encoding='utf-8').read()


setup(
    name='pytest-mp',
    version=version,
    author='Ryan Fitzpatrick',
    author_email='rmfitzpatrick@gmail.com',
    license='MIT',
    url='https://github.com/rmfitzpatrick/pytest-mp',
    description='A test batcher for multiprocessed Pytest runs',
    long_description=read('README.md'),
    py_modules=['pytest_mp'],
    install_requires=['pytest>=3.1.1', 'psutil'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Pytest',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
    ],
    entry_points={
        'pytest11': [
            'pytest-mp = pytest_mp.plugin',
        ],
    },
)
