#!/usr/bin/env python


import sys
import os
from setuptools import setup, find_packages


py_version = sys.version_info[:2]


# Ensure supported python version
if py_version < (3, 0):
    raise RuntimeError('pycons3rt3 does not support Python2, for python2 please use pycons3rt and/or pycons3rtapi')

# Current directory
here = os.path.abspath(os.path.dirname(__file__))


# Get the version
version_txt = os.path.join(here, 'mediamantis/VERSION.txt')
mantis_version = open(version_txt).read().strip()


# Get the requirements
requirements_txt = os.path.join(here, 'cfg/requirements.txt')
requirements = []
with open(requirements_txt) as f:
    for line in f:
        requirements.append(line.strip())


dist = setup(
    name='mediamantis',
    version=mantis_version,
    description='A python application for managing your media files',
    long_description=open('README.md').read(),
    author='Joe Yennaco',
    author_email='helpfuljoe@proton.me',
    url='https://github.com/jyennaco/mac-media-importer-organizer',
    include_package_data=True,
    license='GNU GPL v3',
    packages=find_packages(),
    zip_safe=True,
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'mantis = mediamantis.mediamantis:main'
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent'
    ]
)
