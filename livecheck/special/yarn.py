from collections.abc import Iterator
from pathlib import Path
from shutil import copyfile
from typing import Final, NotRequired, TypedDict, cast
import json
import re
import subprocess as sp

from loguru import logger

from ..utils import check_program
from .utils import EbuildTempFile, get_project_path

CONVERSION_CODE: Final[str] = '''const fs = require('fs');
const lockfile = require('@yarnpkg/lockfile');
console.log(
    JSON.stringify(lockfile.parse(fs.readFileSync(process.argv[3], 'utf8'))['object']));'''

__all__ = ("update_yarn_ebuild", "check_yarn_requirements")


class LockfilePackage(TypedDict):
    dependencies: NotRequired[dict[str, str]]
    integrity: str
    resolved: str
    version: str


Lockfile = dict[str, LockfilePackage]


def create_project(base_package_name: str, yarn_packages: set[str] | None = None) -> Path:
    path = get_project_path(base_package_name)
    sp.run(('yarn', 'config', 'set', 'ignore-engines', 'true'),
           check=True,
           cwd=path,
           stdout=sp.PIPE)
    sp.run(('yarn', 'add', base_package_name) + tuple(yarn_packages or []),
           cwd=path,
           check=True,
           stdout=sp.PIPE)
    sp.run(('yarn', 'upgrade', '--latest', '--non-interactive'),
           cwd=path,
           check=True,
           stdout=sp.PIPE)
    return path


def parse_lockfile(project_path: Path) -> Lockfile:
    return cast(
        Lockfile,
        json.loads(
            sp.run(('node', '-', '--', str(project_path / 'yarn.lock')),
                   input=CONVERSION_CODE,
                   timeout=10,
                   cwd=create_project('@yarnpkg/lockfile'),
                   stdout=sp.PIPE,
                   check=True,
                   text=True).stdout))


def yarn_pkgs(project_path: Path) -> Iterator[str]:
    deps = parse_lockfile(project_path).items()
    for key, val in deps:
        has_prefix_at = key.startswith('@')
        dep_name = f'{"@" if has_prefix_at else ""}{key[1 if has_prefix_at else 0:].split("@", maxsplit=1)[0]}'
        if dep_name.endswith('-cjs'):
            continue
        yield f'{dep_name}-{val["version"]}'


def update_yarn_ebuild(ebuild: str,
                       yarn_base_package: str,
                       pkg: str,
                       yarn_packages: set[str] | None = None) -> None:
    project_path = create_project(yarn_base_package, yarn_packages)
    package_re = re.compile(r'^' + re.escape(yarn_base_package) + r'-[0-9]+')
    in_yarn_pkgs = False
    with EbuildTempFile(ebuild) as temp_file, temp_file.open('w', encoding='utf-8') as tf:
        wrote_new_packages = False
        with Path(ebuild).open('r', encoding='utf-8') as f:
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
                        for new_pkg in sorted(set(yarn_pkgs(project_path)),
                                              key=lambda x: -1 if re.match(package_re, x) else 0):
                            tf.write(f'\t{new_pkg}\n')
                        wrote_new_packages = True
                else:
                    tf.write(line)

        if temp_file.exists() and temp_file.stat().st_size > 0:
            for item in ('package.json', 'yarn.lock'):
                target = Path(ebuild).parent / 'files' / f'{Path(pkg).name}-{item}'
                copyfile(project_path / item, target)
                target.chmod(0o644)


def check_yarn_requirements() -> bool:
    if not check_program('yarn', '--version'):
        logger.error('yarn is not installed')
        return False
    if not check_program('node', '--version'):
        logger.error('yarn is not installed')
        return False
    return True
