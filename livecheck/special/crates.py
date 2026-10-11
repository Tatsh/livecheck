"""Rust dependency downloads and archive generation."""
from __future__ import annotations

from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING
import asyncio
import logging
import os
import re

import tomlkit

from livecheck.utils import check_program

from .utils import build_compress, dist_archive_already_uploaded, remove_url_ebuild, search_ebuild

if TYPE_CHECKING:
    from collections.abc import Mapping

    from livecheck.dist_github import DistGitHubSettings

__all__ = ('check_crates_requirements', 'remove_crates_url', 'remove_native_crates',
           'update_crates_ebuild', 'update_native_crates_ebuild')

log = logging.getLogger(__name__)
_CRATES_ASSIGNMENT = re.compile(r"""^CRATES\+?=(?:"[^"]*"|'[^']*')[ \t]*(?:\#[^\n]*)?$""",
                                re.MULTILINE)
_CRATE_URIS = re.compile(r'\$\{CARGO_CRATE_URIS\}|\$CARGO_CRATE_URIS\b')
_INHERIT = re.compile(r'^inherit[ \t]+(?:[^\n]*\\\n)*[^\n]*', re.MULTILINE)
_SRC_URI_ASSIGNMENT = re.compile(r"""^SRC_URI\+?=["']""", re.MULTILINE)
_SRC_URI_ENTRY = re.compile(r'(\S+)(?:\s+->\s+(\S+))?')
_EMPTY_URI_GROUP = re.compile(r'(?<!\S)[^\s()]+\?\s*\(\s*\)')
_CRATE_NAME = re.compile(r'[A-Za-z0-9_-]+')
_CRATE_VERSION = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.+-]+)?')


def _quoted_value_end(content: str, start: int) -> int:
    delimiters = [content[start]]
    position = start + 1
    while position < len(content):
        character = content[position]
        if character == delimiters[-1]:
            delimiters.pop()
            if not delimiters:
                return position + 1
        elif delimiters[-1] != "'":
            if character == '\\':
                position += 1
            elif content.startswith(('$(', '${'), position):
                delimiters.append(')' if content[position + 1] == '(' else '}')
                position += 1
            elif character in {'"', "'", '`'} and delimiters[-1] not in {'"', '`'}:
                delimiters.append(character)
            elif character == '`' and delimiters[-1] == '"':
                delimiters.append('`')
            elif character == '(' and delimiters[-1] == ')':
                delimiters.append(')')
        position += 1
    msg = 'Unterminated quoted SRC_URI assignment.'
    raise RuntimeError(msg)


def _src_uri_assignments(content: str) -> tuple[tuple[int, int], ...]:
    assignments = []
    end = 0
    for match in _SRC_URI_ASSIGNMENT.finditer(content):
        if match.start() >= end:
            end = _quoted_value_end(content, match.end() - 1)
            assignments.append((match.start(), end))
    return tuple(assignments)


def _remove_crate_downloads(content: str, *, native: bool = False) -> str:
    for start, end in reversed(_src_uri_assignments(content)):
        assignment, _, value = content[start:end].partition('=')
        urls = _SRC_URI_ENTRY.sub(
            lambda entry: '' if any(part and part.endswith('-crates.tar.xz')
                                    for part in entry.groups()) else entry.group(), value[1:-1])
        if native:
            urls = _CRATE_URIS.sub('', urls)
        while (cleaned := _EMPTY_URI_GROUP.sub('', urls)) != urls:
            urls = cleaned
        content = content[:start] + f'{assignment}={value[0]}{urls}{value[-1]}' + content[end:]
    return content


def _locked_crates(source_dir: str) -> tuple[str, ...]:
    lock_path = Path(source_dir) / 'Cargo.lock'
    if not lock_path.is_file() or not (Path(source_dir) / 'Cargo.toml').is_file():
        msg = 'Rust dependencies require Cargo.toml and Cargo.lock in the source directory.'
        raise RuntimeError(msg)
    with lock_path.open(encoding='utf-8') as stream:
        lock = tomlkit.load(stream)
    crates = set()
    for package in lock.get('package', ()):
        source = package.get('source', '')
        if not source:
            continue
        if source != 'registry+https://github.com/rust-lang/crates.io-index':
            msg = f'Unsupported crate source `{source}`. Only crates.io dependencies are supported.'
            raise RuntimeError(msg)
        name, version = package.get('name'), package.get('version')
        if (not isinstance(name, str) or not _CRATE_NAME.fullmatch(name)
                or not isinstance(version, str) or not _CRATE_VERSION.fullmatch(version)):
            msg = 'Invalid crate name or version in Cargo.lock.'
            raise RuntimeError(msg)
        crates.add(f'{name}@{version}')
    return tuple(sorted(crates))


def remove_native_crates(ebuild_content: str) -> str:
    """
    Omit Rust dependencies while fetching and unpacking upstream sources.

    An unterminated quoted ``SRC_URI`` assignment propagates :py:class:`RuntimeError`.

    Parameters
    ----------
    ebuild_content : str
        Ebuild text with native crate downloads or a crate archive.

    Returns
    -------
    str
        Ebuild text without crate downloads.
    """
    content = _remove_crate_downloads(ebuild_content, native=True)
    return _CRATES_ASSIGNMENT.sub('CRATES=""', content)


async def update_native_crates_ebuild(ebuild: str, path: str | None, content: str) -> str:
    """
    Generate native Gentoo crate downloads from upstream Cargo.lock.

    Parameters
    ----------
    ebuild : str
        Ebuild path with crate downloads temporarily removed.
    path : str | None
        Source subdirectory with Cargo.toml and Cargo.lock, or ``None`` to search sources.
    content : str
        Original ebuild text to update.

    Returns
    -------
    str
        Ebuild text with CRATES before inheritance and CARGO_CRATE_URIS in SRC_URI.

    Raises
    ------
    RuntimeError
        If sources cannot be unpacked, Cargo.toml or Cargo.lock is absent, locked crates are
        invalid or unsupported, the ebuild lacks an inherit statement, or a quoted ``SRC_URI``
        assignment is unterminated.
    """
    source_dir, _ = await search_ebuild(ebuild, 'Cargo.lock', path)
    if not source_dir:
        msg = 'Could not locate Cargo.lock in unpacked sources.'
        raise RuntimeError(msg)
    crates = _locked_crates(source_dir)
    content = _remove_crate_downloads(content)
    if not (inherit := _INHERIT.search(content)):
        msg = 'Native crate downloads require an inherit statement in the ebuild.'
        raise RuntimeError(msg)
    crate_list = 'CRATES="\n' + ''.join(f'\t{crate}\n' for crate in crates) + '"'
    if (assignment := _CRATES_ASSIGNMENT.search(content)) and assignment.start() < inherit.start():
        content = _CRATES_ASSIGNMENT.sub(
            lambda match: crate_list if match.start() == assignment.start() else '', content)
    else:
        content = _CRATES_ASSIGNMENT.sub('', content)
        content = content[:inherit.start()] + crate_list + '\n\n' + content[inherit.start():]
    assignments = _src_uri_assignments(content)
    inherit_end = tuple(_INHERIT.finditer(content))[-1].end()
    reset_position = max(
        (start for start, end in assignments if content[start:end].startswith('SRC_URI=')),
        default=0)
    if not any(start >= max(inherit_end, reset_position) and content[start:end].partition('=')
               [2].startswith('"') and _CRATE_URIS.search(content[start:end])
               for start, end in assignments):
        position = max(inherit_end, assignments[-1][1] if assignments else 0)
        content = content[:position] + '\nSRC_URI+=" ${CARGO_CRATE_URIS}"' + content[position:]
    return content


def check_crates_requirements() -> bool:
    """
    Check whether Cargo is available.

    Returns
    -------
    bool
        Whether Cargo can be executed.
    """
    if not check_program('cargo', ['--version']):
        log.error('Cargo is not installed.')
        return False
    return True


def remove_crates_url(ebuild_content: str) -> str:
    """
    Remove the crate archive URL before unpacking sources.

    Parameters
    ----------
    ebuild_content : str
        Ebuild text.

    Returns
    -------
    str
        Ebuild text without the crate archive URL.
    """
    return remove_url_ebuild(ebuild_content, '-crates.tar.xz')


async def update_crates_ebuild(ebuild: str,
                               path: str | None,
                               fetchlist: Mapping[str, tuple[str, ...]],
                               *,
                               dist_settings: DistGitHubSettings | None = None) -> None:
    """
    Download locked crates.io dependencies and build a Gentoo crate archive.

    Archive entries use versioned directories under ``cargo_home/gentoo/``. Skip generation when
    the archive already exists at the configured GitHub release, unless forced.

    Parameters
    ----------
    ebuild : str
        Ebuild path with the crate archive URL temporarily removed.
    path : str | None
        Relative source directory with ``Cargo.toml`` and ``Cargo.lock``, or ``None``
        to search unpacked sources for ``Cargo.lock``.
    fetchlist : Mapping[str, tuple[str, ...]]
        Original fetch map used to derive the archive filename.
    dist_settings : DistGitHubSettings | None
        Optional GitHub release destination.

    Raises
    ------
    RuntimeError
        If sources, dependencies, or archive creation fail, Cargo is unavailable, or
        locked dependencies use sources other than crates.io.
    """
    if await dist_archive_already_uploaded('-crates.tar.xz', fetchlist, dist_settings):
        log.info('Crate archive already uploaded; skipping Cargo.')
        return
    source_dir, temp_dir = await search_ebuild(ebuild, 'Cargo.lock', path)
    if not source_dir:
        msg = 'Could not locate Cargo.lock in unpacked sources.'
        raise RuntimeError(msg)
    _locked_crates(source_dir)
    cargo = which('cargo')
    if cargo is None:
        msg = 'Cargo executable was not found.'
        raise RuntimeError(msg)
    cargo_home = Path(temp_dir) / 'cargo_home'
    vendor_dir = cargo_home / 'gentoo'
    proc = await asyncio.create_subprocess_exec(cargo,
                                                'vendor',
                                                '--config',
                                                'net.offline=false',
                                                '--locked',
                                                '--versioned-dirs',
                                                str(vendor_dir),
                                                cwd=source_dir,
                                                env={
                                                    **os.environ, 'CARGO_HOME': str(cargo_home)
                                                },
                                                stdout=asyncio.subprocess.DEVNULL)
    if await proc.wait() != 0:
        msg = 'Cargo could not download locked crate dependencies.'
        raise RuntimeError(msg)
    if not await build_compress(temp_dir,
                                str(cargo_home),
                                'gentoo',
                                '-crates.tar.xz',
                                fetchlist,
                                dist_settings=dist_settings):
        msg = 'Could not create or upload the crate archive.'
        raise RuntimeError(msg)
