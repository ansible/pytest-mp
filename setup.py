#!/usr/bin/env python
import sys

from setuptools.command.test import test as TestCommand
from setuptools import setup, find_packages


version = '0.0.4'


class Tox(TestCommand):

    user_options = []

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.tox_args = ['-v', '-r']

    def run_tests(self):
        import tox
        errno = tox.cmdline(self.tox_args)
        sys.exit(errno)


setup(name='pytest-mp',
      version=version,
      author='Ryan Fitzpatrick',
      author_email='rmfitzpatrick@gmail.com',
      license='MIT',
      url='https://github.com/ansible/pytest-mp',
      description='A test batcher for multiprocessed Pytest runs',
      long_description_markdown_filename='README.md',
      py_modules=['pytest_mp'],
      packages=find_packages(),
      install_requires=['pytest', 'psutil'],
      setup_requires=['setuptools-markdown'],
      tests_require=['pytest', 'tox'],
      classifiers=['Development Status :: 4 - Beta',
                   'Framework :: Pytest',
                   'Intended Audience :: Developers',
                   'Topic :: Software Development :: Testing',
                   'Programming Language :: Python',
                   'Programming Language :: Python :: 2',
                   'Programming Language :: Python :: 2.7',
                   'Programming Language :: Python :: 3',
                   'Programming Language :: Python :: 3.5',
                   'Programming Language :: Python :: 3.6',
                   'Programming Language :: Python :: Implementation :: CPython',
                   'Operating System :: OS Independent',
                   'License :: OSI Approved :: MIT License'],
      entry_points={'pytest11': ['pytest-mp = pytest_mp.plugin']},
      cmdclass={'test': Tox})
