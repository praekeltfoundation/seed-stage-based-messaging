import os
import re
from setuptools import setup, find_packages


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
    author='Praekelt Foundation',
    author_email='dev@praekeltfoundation.org',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Django==1.9.12',
        'djangorestframework==3.3.2',
        'dj-database-url==0.3.0',
        'psycopg2==2.6.2',
        'raven==5.32.0',
        'django-filter==0.12.0',
        'dj-static==0.0.6',
        'celery==3.1.24',
        'django-celery==3.1.17',
        'redis==2.10.5',
        'pytz==2015.7',
        'requests==2.9.1',
        'go-http==0.3.0',
        'drfdocs==0.0.11',
        'seed-services-client>=0.9.0',
        'croniter==0.3.13',
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
