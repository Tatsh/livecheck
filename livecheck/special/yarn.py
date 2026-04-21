"""Yarn-based ebuild handling."""
from __future__ import annotations

from pathlib import Path
from shutil import copyfile, which
from typing import TYPE_CHECKING, TypedDict, cast
import asyncio
import json
import logging
import re

from anyio import Path as AnyioPath
from livecheck.utils import check_program
from typing_extensions import NotRequired

from .utils import EbuildTempFile, get_project_path

if TYPE_CHECKING:
    from collections.abc import Iterator

CONVERSION_CODE = """const fs = require('fs');
const lockfile = require('@yarnpkg/lockfile');
console.log(
    JSON.stringify(lockfile.parse(fs.readFileSync(process.argv[3], 'utf8'))['object']));"""

__all__ = ('check_yarn_requirements', 'update_yarn_ebuild')

logger = logging.getLogger(__name__)


def _resolved_executable(name: str) -> str:
    path = which(name)
    if path is None:
        msg = f'{name!r} not found in PATH'
        raise FileNotFoundError(msg)
    return path


class LockfilePackage(TypedDict):
    dependencies: NotRequired[dict[str, str]]
    integrity: str
    resolved: str
    version: str


Lockfile = dict[str, LockfilePackage]


async def create_project(base_package_name: str, yarn_packages: set[str] | None = None) -> Path:
    yarn_exe = _resolved_executable('yarn')
    path = get_project_path(base_package_name)
    proc = await asyncio.create_subprocess_exec(yarn_exe,
                                                'config',
                                                'set',
                                                'ignore-engines',
                                                'true',
                                                cwd=str(path),
                                                stdout=asyncio.subprocess.PIPE)
    await proc.wait()
    proc = await asyncio.create_subprocess_exec(yarn_exe,
                                                'add',
                                                base_package_name,
                                                *tuple(yarn_packages or []),
                                                cwd=str(path),
                                                stdout=asyncio.subprocess.PIPE)
    await proc.wait()
    proc = await asyncio.create_subprocess_exec(yarn_exe,
                                                'upgrade',
                                                '--latest',
                                                '--non-interactive',
                                                cwd=str(path),
                                                stdout=asyncio.subprocess.PIPE)
    await proc.wait()
    return path


async def parse_lockfile(project_path: Path) -> Lockfile:
    node_exe = _resolved_executable('node')
    lockfile_project = await create_project('@yarnpkg/lockfile')
    proc = await asyncio.create_subprocess_exec(node_exe,
                                                '-',
                                                '--',
                                                str(project_path / 'yarn.lock'),
                                                cwd=str(lockfile_project),
                                                stdin=asyncio.subprocess.PIPE,
                                                stdout=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate(input=CONVERSION_CODE.encode())
    return cast('Lockfile', json.loads(stdout.decode()))


def yarn_pkgs(lockfile: Lockfile) -> Iterator[str]:
    for key, val in lockfile.items():
        has_prefix_at = key.startswith('@')
        suffix = key[1 if has_prefix_at else 0:].split('@', maxsplit=1)[0]
        dep_name = f'{"@" if has_prefix_at else ""}{suffix}'
        if dep_name.endswith('-cjs'):
            continue
        yield f'{dep_name}-{val["version"]}'


def _yarn_package_lines(lockfile: Lockfile, package_re: re.Pattern[str]) -> list[str]:
    """
    Return sorted yarn package lines.

    Returns
    -------
    list[str]
        Tab-indented, newline-terminated package lines sorted with the base package first.
    """
    return [
        f'\t{new_pkg}\n' for new_pkg in sorted(set(yarn_pkgs(lockfile)),
                                               key=lambda x: -1 if re.match(package_re, x) else 0)
    ]


async def update_yarn_ebuild(ebuild: str,
                             yarn_base_package: str,
                             pkg: str,
                             yarn_packages: set[str] | None = None) -> None:
    """
    Update a Yarn-based ebuild.

    Raises
    ------
    RuntimeError
        If the ``YARN_PKGS`` section is malformed.
    """
    project_path = await create_project(yarn_base_package, yarn_packages)
    lockfile = await parse_lockfile(project_path)
    package_re = re.compile(r'^' + re.escape(yarn_base_package) + r'-[0-9]+')
    in_yarn_pkgs = False
    written_new_pkgs = False
    async with EbuildTempFile(ebuild) as temp_file:
        ebuild_text = await AnyioPath(ebuild).read_text(encoding='utf-8')
        out: list[str] = []
        for line in ebuild_text.splitlines(keepends=True):
            if line.startswith('YARN_PKGS=('):
                out.append(line)
                if in_yarn_pkgs:
                    raise RuntimeError
                in_yarn_pkgs = True
            elif in_yarn_pkgs:
                if line.strip() == ')':
                    if not written_new_pkgs:
                        out.extend(_yarn_package_lines(lockfile, package_re))
                    in_yarn_pkgs = False
                    out.append(line)
                elif not written_new_pkgs:
                    out.extend(_yarn_package_lines(lockfile, package_re))
                    written_new_pkgs = True
            else:
                out.append(line)
        await AnyioPath(temp_file).write_text(''.join(out), encoding='utf-8')
    for item in ('package.json', 'yarn.lock'):
        target = Path(ebuild).parent / 'files' / f'{Path(pkg).name}-{item}'
        copyfile(project_path / item, target)
        target.chmod(0o644)


def check_yarn_requirements() -> bool:
    """
    Check if Yarn and Node are installed.

    Returns
    -------
    bool
        ``True`` if both ``yarn`` and ``node`` are available, otherwise ``False``.
    """
    if not check_program('yarn', ['--version']):
        logger.error('yarn is not installed')
        return False
    if not check_program('node', ['--version']):
        logger.error('yarn is not installed')
        return False
    return True
