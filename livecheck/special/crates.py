"""Rust crate archive generation."""
from __future__ import annotations

from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING
import asyncio
import logging

import tomlkit

from livecheck.utils import check_program

from .utils import build_compress, dist_archive_already_uploaded, remove_url_ebuild, search_ebuild

if TYPE_CHECKING:
    from collections.abc import Mapping

    from livecheck.dist_github import DistGitHubSettings

__all__ = ('check_crates_requirements', 'remove_crates_url', 'update_crates_ebuild')

log = logging.getLogger(__name__)


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
    lock_path = Path(source_dir) / 'Cargo.lock'
    if not lock_path.is_file() or not (Path(source_dir) / 'Cargo.toml').is_file():
        msg = 'Crate archives require Cargo.toml and Cargo.lock in the selected source directory.'
        raise RuntimeError(msg)
    with lock_path.open(encoding='utf-8') as stream:
        lock = tomlkit.load(stream)
    for package in lock.get('package', ()):
        source = package.get('source', '')
        if source and source != 'registry+https://github.com/rust-lang/crates.io-index':
            msg = 'Crate archives currently support crates.io dependencies only.'
            raise RuntimeError(msg)
    cargo = which('cargo')
    if cargo is None:
        msg = 'Cargo executable was not found.'
        raise RuntimeError(msg)
    cargo_home = Path(temp_dir) / 'cargo_home'
    vendor_dir = cargo_home / 'gentoo'
    proc = await asyncio.create_subprocess_exec(cargo,
                                                'vendor',
                                                '--locked',
                                                '--versioned-dirs',
                                                str(vendor_dir),
                                                cwd=source_dir,
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
