#!/usr/bin/env python3

import os
import re
import itertools
import argparse
import sys
import subprocess
import hashlib
import zipfile
import functools
import traceback
import tarfile
import urllib.parse
import abc
import locale
import json
import glob

metadata_ext = '.metadata.json'

class Metadata:

    __slots__ = [
        'name',
        'norm_name',
        'version',
        'homepage',
        'trusted',
        'sha256'
    ]

    def __init__(self, name, norm_name, version,
                 homepage, trusted=True, sha256=''):
        self.name = name
        self.norm_name = norm_name
        self.version = version
        self.homepage = homepage
        self.trusted = trusted
        self.sha256 = sha256

class Pkg:

    __slots__ = ['file', 'metadata']

    def __init__(self, file_, metadata):
        self.file = file_
        self.metadata = metadata

def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()

def parse_pkg_metadata(metadata):
    m = re.search(rb'^Name: (.*)$', metadata, re.MULTILINE)
    if not m:
        raise Exception('invalid metadata file')
    name = m.group(1).decode('utf-8').strip()
    m = re.search(rb'^Version: (.*)$', metadata, re.MULTILINE)
    if not m:
        raise Exception('invalid metadata file')
    version = m.group(1).decode('utf-8').strip()
    m = re.search(rb'^Home-page: (.*)$', metadata, re.MULTILINE)
    if not m:
        raise Exception('invalid metadata file')
    homepage = m.group(1).decode('utf-8').strip()
    return Metadata(name, normalize(name), version, homepage)

def get_metadata_from_archive(f, extension, extract_fn, member='PKG-INFO'):
    f_name = os.path.basename(f)
    idx = f_name.find(extension)
    if idx == -1:
        raise Exception('invalid archive file name')
    prefix = f_name[:idx]
    metadata_file = os.path.join(prefix, member)
    try:
        metadata = extract_fn(metadata_file).read()
    except KeyError:
        try:
            name, version = prefix.rsplit('-', 1)
        except ValueError as e:
            raise Exception('unable to extract metadata')
        return Metadata(name, normalize(name), version, '')
    return parse_pkg_metadata(metadata)

def get_metadata_from_wheel(f):
    whl = zipfile.ZipFile(f)
    whl_name = os.path.basename(f)
    prefix = '-'.join(whl_name.split('-', 2)[:2])
    metadata_file = os.path.join(prefix + '.dist-info', 'METADATA')
    try:
        metadata = whl.open(metadata_file).read()
    except KeyError:
        raise Exception('metadata file not found')
    metadata = parse_pkg_metadata(metadata)
    if not whl_name.startswith(metadata.name):
        # It means that the package name contains hyphens or
        # underscores. Try to find out the real name of the package
        # using the homepage. It's ugly but I don't know a better way
        # to do it
        metadata.trusted = False
        homepage_path = urllib.parse.urlparse(metadata.homepage).path
        if homepage_path and homepage_path[0] == '/':
            if homepage_path[-1] == '/':
                homepage_path = homepage_path[:-1]
            if homepage_path:
                _, basename = homepage_path.rsplit('/', 1)
                if whl_name.startswith(basename):
                    metadata.name = basename
    return metadata

def get_metadata_from_zip(f):
    zip_ = zipfile.ZipFile(f)
    return get_metadata_from_archive(f, '.zip', zip_.open)

def get_metadata_from_tar(f, extension='.tar.gz'):
    tar = tarfile.open(f)
    return get_metadata_from_archive(f, extension, tar.extractfile)

_metadata_getter = {
    '.whl': get_metadata_from_wheel,
    '.zip': get_metadata_from_zip,
    '.tar.gz': get_metadata_from_tar,
    '.tar.bz2': functools.partial(get_metadata_from_tar, extension='.tar.bz2')
}

def get_metadata_from_json(f):
    metadata = None
    try:
        metadata_json = json.load(open(f + metadata_ext))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    else:
        try:
            metadata = Metadata(**metadata_json)
        except TypeError:
            pass
    return metadata

def get_pkg_metadata(f):
    metadata = get_metadata_from_json(f)
    if metadata:
        return metadata
    for extension, getter in _metadata_getter.items():
        if f.endswith(extension):
            metadata = getter(f)
            h = hashlib.sha256(open(f, 'rb').read()).hexdigest()
            metadata.sha256 = h
            return metadata
    else:
        raise Exception('unknown extension')

def get_pkg(f):
    try:
        return Pkg(f, get_pkg_metadata(f))
    except Exception as e:
        raise Exception("error while processing '{}': {}".format(f, str(e)))

def fix_pkg_names(pkgs):
    sort_fn = lambda p: p.metadata.trusted
    sorted_pkgs = sorted(pkgs, key=sort_fn, reverse=True)
    trusted_name = None
    for trusted, pkgs in itertools.groupby(sorted_pkgs, sort_fn):
        if trusted:
            trusted_name = next(pkgs).metadata.name
        elif trusted_name is not None:
            for pkg in pkgs:
                pkg.metadata.name = trusted_name

def download(pkgs,
             requirements=[],
             dest='.',
             index_url=None,
             allow_binary=False,
             platform=None,
             python_version=None,
             implementation=None,
             abi=None,
             pip='pip'):
    args = [pip, 'download', '-d', dest]
    if index_url:
        args += ['--index-url', index_url]
    if not allow_binary:
        args += ['--no-binary', ':all:']
    if platform or python_version or implementation or abi:
        args += ['--only-binary', ':all:']
    if platform:
        args += ['--platform', platform]
    if python_version:
        args += ['--python-version', python_version]
    if implementation:
        args += ['--implementation', implementation]
    if abi:
        args += ['--abi', abi]
    for r in requirements:
        args += ['-r', r]
    args += pkgs
    subprocess.check_call(args)

def list_dir(d, test=os.path.isfile):
    return [
        os.path.join(d, f)
        for f in os.listdir(d) if test(os.path.join(d, f))
    ]

def list_pkgs(download_dir, fix_names=True):
    test = lambda f: not f.endswith(metadata_ext)
    all_pkgs = [get_pkg(f) for f in list_dir(download_dir, test)]
    if fix_names:
        sort_fn = lambda p: p.metadata.norm_name
        sorted_pkgs = sorted(all_pkgs, key=sort_fn)
        for _, pkgs in itertools.groupby(sorted_pkgs, sort_fn):
            fix_pkg_names(pkgs)
    return all_pkgs

def list_pkg_by_names(download_dir):
    sort_fn = lambda p: locale.strxfrm(p.metadata.name)
    pkgs = sorted(list_pkgs(download_dir), key=sort_fn)
    return itertools.groupby(pkgs, lambda p: p.metadata.name)

def list_pkg_names(download_dir):
    return [pkg_name for pkg_name, _ in list_pkg_by_names(download_dir)]

def generate_root_html(pkg_names):
    html_tmpl = '''\
<!DOCTYPE html>
<html>
  <head>
    <title>Simple index</title>
  </head>
  <body>
    {}
  </body>
</html>'''
    anchor_tmpl = '<a href="{0}">{1}</a>'
    anchors = '\n    '.join(
        anchor_tmpl.format(norm_name, name)
        for norm_name, name in pkg_names
    )
    return html_tmpl.format(anchors)

def generate_pkg_html(pkgs):
    html_tmpl = '''\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for {0}</title>
  </head>
  <body>
    <h1>Links for {0}</h1>
    {1}
  </body>
</html>'''
    anchor_tmpl = '<a href="{0}#sha256={1}">{0}</a><br/>'
    anchors = []
    for pkg in pkgs:
        h = pkg.metadata.sha256
        anchors.append(anchor_tmpl.format(os.path.basename(pkg.file), h))
    return html_tmpl.format(pkgs[0].metadata.name, '\n    '.join(anchors))

def write_html_index(d, html):
    with open(os.path.join(d, 'index.html'), 'w') as f:
        f.write(html)

def create_mirror(download_dir='.', mirror_dir='.', pkgs=None):
    pkgs = pkgs if pkgs is not None else list_pkgs(download_dir, False)
    sort_fn = lambda p: p.metadata.norm_name
    sorted_pkgs = sorted(pkgs, key=sort_fn)
    pkg_names = []
    for pkg_norm_name, pkgs in itertools.groupby(sorted_pkgs, sort_fn):
        pkg_dir = os.path.join(mirror_dir, pkg_norm_name)
        os.makedirs(pkg_dir, exist_ok=True)
        pkgs = list(pkgs)
        fix_pkg_names(pkgs)
        for pkg in pkgs:
            dest = os.path.join(pkg_dir, os.path.basename(pkg.file))
            try:
                os.symlink(os.path.relpath(pkg.file, pkg_dir), dest)
            except FileExistsError:
                pass
        pkg_html = generate_pkg_html(pkgs)
        write_html_index(pkg_dir, pkg_html)
        pkg_names.append((pkg_norm_name, pkgs[0].metadata.name))
    root_html = generate_root_html(pkg_names)
    write_html_index(mirror_dir, root_html)

def create_metadata_files(download_dir, overwrite=False):
    if overwrite:
        metadata_glob = os.path.join(download_dir, '*' + metadata_ext)
        for metadata_file in glob.glob(metadata_glob):
            os.unlink(metadata_file)
    for pkg in list_pkgs(download_dir):
        metadata_file = pkg.file + metadata_ext
        if os.path.exists(metadata_file):
            continue
        with open(metadata_file, 'w') as f:
            metadata = {
                attr: getattr(pkg.metadata, attr)
                for attr in Metadata.__slots__
            }
            json.dump(metadata, f)

class CmdMeta(abc.ABCMeta):

    _registered = {}

    def __new__(cls, name, bases, ns):
        c = super().__new__(cls, name, bases, ns)
        ignore = ns.get('__cmd_ignore__', False)
        if ignore:
            return c
        cmd_name = ns.get('__cmd_name__', '')
        if not cmd_name:
            m = re.match(r'(.*)Cmd$', name)
            if m is not None:
                cmd_name = m.group(1).lower()
        if cmd_name:
            cmd_help = ns.get('__cmd_help__', cmd_name)
            cls._registered[cmd_name] = c, cmd_help
        return c

    @property
    def registered(cls):
        return cls._registered

class Cmd(metaclass=CmdMeta):

    @classmethod
    @abc.abstractmethod
    def add_args(cls, parser):
        pass

    @abc.abstractmethod
    def run(self, args):
        os.makedirs(args.download_dir, exist_ok=True)

class ListCmd(Cmd):

    __cmd_help__ = 'list packages'

    @classmethod
    def add_args(cls, parser):
        parser.add_argument(
            '--name-only',
            action='store_true',
            help='list only the name of the packages'
        )
        parser.add_argument(
            '-n',
            '--name',
            metavar='NAME',
            help='list only the versions of %(metavar)s'
        )

    def run(self, args):
        super().run(args)
        pkg_by_names = list_pkg_by_names(args.download_dir)
        for pkg_name, pkgs in pkg_by_names:
            if args.name is not None and pkg_name != args.name:
                continue
            print(pkg_name)
            if args.name is None and args.name_only:
                continue
            for version in {p.metadata.version for p in pkgs}:
                print('  {}'.format(version))

class DownloadCmd(Cmd):

    __cmd_help__ = 'download packages and their dependencies'

    @classmethod
    def add_args(cls, parser):
        parser.add_argument(
            '-i',
            '--index-url',
            help='base URL of Python Package Index'
        )
        parser.add_argument(
            '-p',
            '--pip-executable',
            default='pip',
            help='pip executable to use [%(default)s]'
        )
        parser.add_argument(
            '-b',
            '--binary',
            action='store_true',
            help='allow the downloading of binary package'
        )
        parser.add_argument(
            '-k',
            '--keep-going',
            action='store_true',
            help='keep going if pip failed to download a package'
        )
        parser.add_argument(
            '--platform',
            metavar='PLATFORM',
            help='only download wheels compatible with %(metavar)s. '
                 'This option implies --binary.'
        )
        parser.add_argument(
            '--python-version',
            metavar='VERSION',
            help='only download wheels compatible with Python interpreter '
                 'version %(metavar)s. This option implies --binary.'
        )
        parser.add_argument(
            '--implementation',
            metavar='IMPL',
            help='only download wheels compatible with Python '
                 'implementation %(metavar)s. This option implies --binary.'
        )
        parser.add_argument(
            '--abi',
            metavar='ABI',
            help='only download wheels compatible with Python '
                 'abi %(metavar)s. This option implies --binary.'
        )
        parser.add_argument(
            '-r',
            '--requirement',
            dest='requirements',
            default=[],
            action='append',
            metavar='FILE',
            help='add packages from the given requirements file. '
                 'This option can be used multiple times.'
        )
        parser.add_argument(
            'pkgs',
            nargs='*',
            help='packages to download'
        )

    def run(self, args):
        super().run(args)
        if (args.platform or
            args.python_version or
            args.implementation or
            args.abi):
            args.binary = True
        download_ = functools.partial(
            download,
            dest=args.download_dir,
            index_url=args.index_url,
            allow_binary=args.binary,
            platform=args.platform,
            python_version=args.python_version,
            implementation=args.implementation,
            abi=args.abi,
            pip=args.pip_executable
        )
        pkgs = args.pkgs
        if not pkgs and not args.requirements:
            pkgs = list_pkg_names(args.download_dir)
        if args.keep_going:
            for pkg in pkgs:
                try:
                    download_([pkg])
                except subprocess.CalledProcessError:
                    traceback.print_exc()
            for r in args.requirements:
                try:
                    download_([], [r])
                except subprocess.CalledProcessError:
                    traceback.print_exc()
        else:
            download_(pkgs, args.requirements)
        create_metadata_files(args.download_dir)

class MirrorCmd(Cmd):

    __cmd_ignore__ = True

    @classmethod
    def add_args(cls, parser):
        parser.add_argument(
            '-m',
            '--mirror-dir',
            required=True,
            metavar='DIR',
            help='create the mirror into %(metavar)s'
        )

    def run(self, args):
        super().run(args)
        os.makedirs(args.mirror_dir, exist_ok=True)

class CreateCmd(MirrorCmd):

    __cmd_help__ = 'create the mirror'

    def run(self, args):
        super().run(args)
        create_mirror(args.download_dir, args.mirror_dir)

class DeleteCmd(MirrorCmd):

    __cmd_help__ = 'delete a package, use at your own risk!'

    @classmethod
    def add_args(cls, parser):
        super().add_args(parser)
        parser.add_argument(
            '-n',
            '--name',
            required=True,
            metavar='NAME',
            help='remove package with %(metavar)s'
        )
        parser.add_argument(
            '-v',
            '--version',
            metavar='VERSION',
            help='remove only the package version %(metavar)s'
        )

    def run(self, args):
        super().run(args)
        download_dir = args.download_dir
        mirror_dir = args.mirror_dir
        pkgs = list_pkgs(download_dir)
        new_pkgs = []
        for pkg in pkgs:
            if pkg.metadata.name == args.name:
                if (args.version is None or
                    args.version == pkg.metadata.version):
                    basename = os.path.basename(pkg.file)
                    norm_name = pkg.metadata.norm_name
                    try:
                        os.unlink(os.path.join(mirror_dir, norm_name, basename))
                    except FileNotFoundError:
                        pass
                    try:
                        os.unlink(pkg.file + metadata_ext)
                    except FileNotFoundError:
                        pass
                    os.unlink(pkg.file)
                    continue
            new_pkgs.append(pkg)
        create_mirror(download_dir, mirror_dir, new_pkgs)

class WriteMetadataCmd(Cmd):

    __cmd_name__ = 'write-metadata'
    __cmd_help__ = 'create metadata files'

    @classmethod
    def add_args(cls, parser):
        parser.add_argument(
            '-o',
            '--overwrite',
            action='store_true',
            help='overwrite metadata files'
        )

    def run(self, args):
        super().run(args)
        create_metadata_files(args.download_dir, args.overwrite)

def main():
    locale.setlocale(locale.LC_ALL, '')
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d',
        '--download-dir',
        required=True,
        metavar='DIR',
        help='download directory'
    )
    subparsers = parser.add_subparsers(dest='cmd', metavar='CMD')
    for cmd_name, (cmd_class, cmd_help) in Cmd.registered.items():
        cmd_parser = subparsers.add_parser(cmd_name, help=cmd_help)
        cmd_class.add_args(cmd_parser)
    args = parser.parse_args()
    if args.cmd is None:
        print('You must specify a command.')
        parser.print_help()
        return 1
    cmd_class, _ = Cmd.registered[args.cmd]
    cmd = cmd_class()
    try:
        cmd.run(args)
    except Exception as e:
        print("Failed to execute command '{}': {}".format(args.cmd, str(e)))
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
