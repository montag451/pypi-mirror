from setuptools import setup

setup(
    name="python-pypi-mirror",
    version="5.0.0",
    author="montag451",
    author_email="montag451@laposte.net",
    maintainer="montag451",
    maintainer_email="montag451@laposte.net",
    url="https://github.com/montag451/pypi-mirror",
    description="A script to create a partial PyPI mirror",
    long_description=open("README.rst").read(),
    python_requires=">=3.7",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    py_modules=["pypi_mirror"],
    entry_points={"console_scripts": ["pypi-mirror=pypi_mirror:main"]},
)
