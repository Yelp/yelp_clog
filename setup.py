# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name='yelp-clog',
    version='2.2.9',
    description='A package which provides logging and reading from scribe.',
    author='Yelp Infra Team',
    author_email='infra@yelp.com',
    packages=['clog'],
    package_data={
        'clog': ['fb303.thrift', 'scribe.thrift'],
    },
    install_requires=[
        'boto>=2.0.0',
        'future>=0.14.0',
        'thriftpy==0.1.15',
        'PyStaticConfiguration >= 0.8',
        'simplejson',
    ]
)
