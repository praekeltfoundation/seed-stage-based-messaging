import codecs
import os
import re

from setuptools import setup, find_packages


HERE = os.path.abspath(os.path.dirname(__file__))


def read(*parts):  # Stolen from txacme
    with codecs.open(os.path.join(HERE, *parts), 'rb', 'utf-8') as f:
        return f.read()


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)


version = get_version('seed_stage_based_messaging')


setup(
    name="seed-stage-based-messaging",
    version=version,
    url='http://github.com/praekelt/seed-stage-based-messaging',
    license='BSD',
    description='Seed Stage Based Messaging microservice',
    long_description=read('README.rst'),
    author='Praekelt.org',
    author_email='dev@praekelt.org',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Django==1.9.12',
        'djangorestframework==3.3.2',
        'dj-database-url==0.3.0',
        'psycopg2==2.7.1',
        'raven==5.32.0',
        'django-filter==0.12.0',
        'dj-static==0.0.6',
        'celery==3.1.24',
        'django-celery==3.1.17',
        'redis==2.10.5',
        'pytz==2015.7',
        'requests==2.9.1',
        'drfdocs==0.0.11',
        'seed-services-client>=0.31.0',
        'croniter==0.3.13',
        'django-cache-url==1.3.1',
        'django-redis==4.7.0',
        'sftpclone==1.2',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
