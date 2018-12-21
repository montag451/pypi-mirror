from setuptools import setup, find_packages

setup(
    name='python-pypi-mirror',
    version='1.0.0',
    author='montag451',
    author_email='montag451@laposte.net',
    maintainer='montag451',
    maintainer_email='montag451@laposte.net',
    url='https://github.com/montag451/pypi_mirror',
    description='A script to create a partial PyPI mirror',
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
    ],
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'pypi_mirror=pypi_mirror:main'
        ]
    }
)
