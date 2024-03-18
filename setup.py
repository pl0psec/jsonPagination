"""
setup.py for jsonPagination package.

This script is used to define the jsonPagination package attributes for distribution.
It includes package metadata like name, version, author, and description.
"""

from setuptools import setup, find_packages

# Read the contents of your README file
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='jsonPagination',
    version='0.1.1',
    author='pl0psec',
    author_email='contact@pl0psec.com',
    description='A versatile JSON data downloader with pagination and multithreading support.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/pl0psec/jsonPagination',
    packages=find_packages(),
    install_requires=[
        'requests',
        'tqdm',
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
