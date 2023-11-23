from functools import lru_cache
from pathlib import Path
from shutil import copyfile
from typing import Final, Iterator, TypedDict, cast
import json
import subprocess as sp
import tempfile

from typing_extensions import NotRequired

from .utils import get_project_path

CONVERSION_CODE: Final[str] = '''const fs = require('fs');
const lockfile = require('@yarnpkg/lockfile');
console.log(
    JSON.stringify(lockfile.parse(fs.readFileSync(process.argv[3], 'utf8'))['object']));'''


class LockfilePackage(TypedDict):
    dependencies: NotRequired[dict[str, str]]
    integrity: str
    resolved: str
    version: str


Lockfile = dict[str, LockfilePackage]


@lru_cache
def create_project(package_name: str) -> Path:
    path = get_project_path(package_name)
    sp.run(('yarn', 'add', package_name), cwd=path, check=True, stdout=sp.PIPE)
    sp.run(('yarn', 'upgrade', '--latest', '--non-interactive'),
           cwd=path,
           check=True,
           stdout=sp.PIPE)
    return path


def parse_lockfile(package_name: str) -> Lockfile:
    return cast(
        Lockfile,
        json.loads(
            sp.run(('node', '-', '--', str(create_project(package_name) / 'yarn.lock')),
                   input=CONVERSION_CODE,
                   timeout=10,
                   cwd=create_project('@yarnpkg/lockfile'),
                   stdout=sp.PIPE,
                   check=True,
                   text=True).stdout))


def yarn_pkgs(package_name: str) -> Iterator[str]:
    for key, val in parse_lockfile(package_name).items():
        has_prefix_at = key.startswith('@')
        dep_name = f'{"@" if has_prefix_at else ""}{key[1 if has_prefix_at else 0:].split("@", maxsplit=1)[0]}'
        if dep_name.endswith('-cjs'):
            continue
        yield f'{dep_name}-{val["version"]}'


def update_yarn_ebuild(ebuild: str | Path, yarn_base_package: str, pkg: str) -> None:
    project_path = get_project_path(yarn_base_package)
    new_yarn_pkgs = yarn_pkgs(yarn_base_package)
    ebuild = Path(ebuild)
    in_yarn_pkgs = False
    tf = tempfile.NamedTemporaryFile(mode='w',
                                     prefix=ebuild.stem,
                                     suffix=ebuild.suffix,
                                     delete=False,
                                     dir=ebuild.parent)
    wrote_new_packages = False
    with ebuild.open('r') as f:
        for line in f.readlines():
            if line.startswith('YARN_PKGS=('):
                tf.write(line)
                if in_yarn_pkgs:
                    raise RuntimeError
                in_yarn_pkgs = True
            elif in_yarn_pkgs:
                if line.strip() == ')':
                    in_yarn_pkgs = False
                    tf.write(line)
                elif not wrote_new_packages:
                    for pkg in new_yarn_pkgs:
                        tf.write(f'\t{pkg}\n')
                    wrote_new_packages = True
            else:
                tf.write(line)
    ebuild.unlink()
    Path(tf.name).rename(ebuild).chmod(0o0644)
    for item in ('package.json', 'yarn.lock'):
        target = ebuild.parent / 'files' / f'{pkg}-{item}'
        copyfile(project_path / item, target)
        target.chmod(0o644)
