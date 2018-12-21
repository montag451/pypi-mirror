`pypi_mirror` is a small script to generate a partial PyPI mirror. It
relies on `pip` to do the most difficult part of the job (downloading
a package and its dependencies).

# Why?

Because most of the time you don't need a full PyPI mirror but only a
mirror that contains the packages you use. If you want a full PyPI
mirror you should look at
[bandersnatch](https://github.com/pypa/bandersnatch.git).

# Installation

You can install `pypi_mirror` using `pip`:

```sh
pip install python-pypi-mirror
```

Or, as the script doesn't have any external dependencies, you can
simply copy the script to the location of your choice to use it.

# How to use it?

The script provides several commands to manage your mirror. To find
out which commands are available, type:

```sh
pypi_mirror --help
```

Every command provides its own help message. So for example to get the
help message of the `download` command, type:

```sh
pypi_mirror download --help
```

The commands that you will probably use the most are the `download`
command and the `create` command. For example to create a mirror which
contains the `requests` package and its dependencies, you can type the
following:

``` sh
pypi_mirror -d downloads download requests
pypi_mirror -d downloads create -m simple
```

The first command will create a `downloads` directory into the current
directory and use `pip` to download the `requests` package and its
dependencies into the newly created directory. Then the `create`
command will create a `simple` directory into the current directory
and will build the mirror inside this newly created directory. You can
add new packages by repeating this sequence of commands.

To make your mirror available through HTTP, you can point your HTTP
server of choice to the `simple` directory. For exemple, type the
following command into the current directory:

```sh
python3 -m http.server
```

It will start a HTTP server that will serve file from the current
directory (which should contains the `downloads` directory and the
`simple` directory). You can then install packages using your brand
new mirror using the following command:

```sh
pip install -i http://127.0.0.1:8000/simple requests
```
