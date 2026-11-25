"""Composer functions."""
from __future__ import annotations

from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING, Literal
import asyncio
import logging

from livecheck.utils import check_program

from .utils import (
    build_compress,
    build_digest_archive,
    dist_archive_already_uploaded,
    remove_url_ebuild,
    search_ebuild,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from livecheck.dist_github import DistGitHubSettings

__all__ = ('check_composer_requirements', 'remove_composer_url', 'update_composer_ebuild')

log = logging.getLogger(__name__)


def remove_composer_url(ebuild_content: str) -> str:
    """
    Remove the URL for the vendor tarball from the ebuild content.

    Parameters
    ----------
    ebuild_content : str
        Full ebuild file text.

    Returns
    -------
    str
        Ebuild text without the vendor tarball URL line.
    """
    return remove_url_ebuild(ebuild_content, '-vendor.tar.xz')


async def update_composer_ebuild(ebuild: str,
                                 path: str | None,
                                 fetchlist: Mapping[str, tuple[str, ...]],
                                 *,
                                 archive_mode: Literal['lockfile', 'version'] = 'version',
                                 dist_settings: DistGitHubSettings | None = None,
                                 previous_digest: str | None = None) -> str | None:
    """
    Update a Composer package ebuild.

    In ``lockfile`` mode the vendor archive is named after a digest of the installed files, and its
    member paths are relative to the directory of ``composer.json``.

    Parameters
    ----------
    ebuild : str
        Path to the ebuild file.
    path : str | None
        Optional subdirectory path inside the unpacked sources.
    fetchlist : Mapping[str, tuple[str, ...]]
        Fetch map used when compressing vendor output.
    archive_mode : Literal['lockfile', 'version']
        Whether the archive is named after the package version or after the dependency digest.
    dist_settings : DistGitHubSettings | None
        Optional GitHub release destination for the produced archive.
    previous_digest : str | None
        Dependency digest of the archive that the previous version uses, if any.

    Returns
    -------
    str | None
        In ``lockfile`` mode, the digest in the name of the archive for the ebuild. ``None`` in
        ``version`` mode and on failure.
    """
    lockfile_mode = archive_mode == 'lockfile'
    if not lockfile_mode and await dist_archive_already_uploaded('-vendor.tar.xz', fetchlist,
                                                                 dist_settings):
        log.info('Vendor archive already uploaded; skipping `composer install`.')
        return None
    composer_path, temp_dir = await search_ebuild(ebuild, 'composer.json', path)
    if not composer_path:
        return None

    composer_exe = which('composer')
    if composer_exe is None:
        log.error('composer executable not found in PATH')
        return None
    try:
        proc = await asyncio.create_subprocess_exec(composer_exe,
                                                    '--no-interaction',
                                                    '--no-scripts',
                                                    'install',
                                                    cwd=composer_path)
        returncode = await proc.wait()
        if returncode != 0:
            log.error("Error running 'composer'.")
            return None
    except OSError:
        log.exception("Error running 'composer'.")
        return None

    if lockfile_mode:
        return await build_digest_archive(composer_path,
                                          'vendor',
                                          '-vendor.tar.xz',
                                          Path(ebuild).parent.name,
                                          dist_settings=dist_settings,
                                          previous_digest=previous_digest)
    await build_compress(temp_dir,
                         composer_path,
                         'vendor',
                         '-vendor.tar.xz',
                         fetchlist,
                         dist_settings=dist_settings)
    return None


def check_composer_requirements() -> bool:
    """
    Check if Composer is installed.

    Returns
    -------
    bool
        ``True`` if ``composer`` is available, otherwise ``False``.
    """
    if not check_program('composer', ['--version']):
        log.error('composer is not installed')
        return False
    return True
