# Use setuptools if we can
try:
    from setuptools.core import setup
except ImportError:
    from distutils.core import setup

PACKAGE = 'django_override_db_tables'
VERSION = '0.2'

setup(
    name=PACKAGE, version=VERSION,
    description="Context manager for overriding Django ORM database tables.",
    author='Rockabox Media Ltd',
    author_email='tech@rockabox.com',
    packages=[
        'django_override_db_tables',
    ],
    license='MIT',
    install_requires=[
        'Django>=1.6.0',
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'Framework :: Django',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
    ],
)
