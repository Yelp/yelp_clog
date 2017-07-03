# -*- coding: utf-8 -*-
# Copyright 2015 Yelp Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from setuptools import setup

setup(
    name='yelp-clog',
    version='2.7.3',
    description='A package which provides logging and reading from scribe.',
    author='Yelp Infra Team',
    author_email='infra@yelp.com',
    packages=['clog'],
    package_data={'clog': ['fb303.thrift', 'scribe.thrift']},
    install_requires=[
        'boto>=2.0.0',
        'thriftpy',
        'PyStaticConfiguration >= 0.10.3',
        'simplejson',
        'six>=1.4.0',
    ],
    extras_require={
        'uwsgi': ['uWSGI'],
        'internal': ['yelp_meteorite']
    },
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
)
