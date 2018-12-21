from setuptools import setup

setup(
    name='python-pypi-mirror',
    version='1.0.1',
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
    py_modules=['pypi_mirror'],
    entry_points={
        'console_scripts': [
            'pypi_mirror=pypi_mirror:main'
        ]
    }
)
