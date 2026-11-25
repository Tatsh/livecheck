"""Golang (go-module) utilities."""
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

__all__ = ('check_gomodule_requirements', 'remove_gomodule_url', 'update_gomodule_ebuild')

logger = logging.getLogger(__name__)


def remove_gomodule_url(ebuild_content: str) -> str:
    """
    Remove ``-vendor.tar.xz`` line from ebuild.

    Parameters
    ----------
    ebuild_content : str
        Full ebuild file text.

    Returns
    -------
    str
        Ebuild text without the vendor archive URL line.
    """
    return remove_url_ebuild(ebuild_content, '-vendor.tar.xz')


async def update_gomodule_ebuild(ebuild: str,
                                 path: str | None,
                                 fetchlist: Mapping[str, tuple[str, ...]],
                                 *,
                                 archive_mode: Literal['lockfile', 'version'] = 'version',
                                 dist_settings: DistGitHubSettings | None = None,
                                 previous_digest: str | None = None) -> str | None:
    """
    Update a Go module-based ebuild.

    In ``lockfile`` mode the vendor archive is named after a digest of the vendored files, and its
    member paths are relative to the directory of ``go.mod``.

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
        logger.info('Vendor archive already uploaded; skipping `go mod vendor`.')
        return None
    go_mod_path, temp_dir = await search_ebuild(ebuild, 'go.mod', path)
    if not go_mod_path:
        return None

    go_exe = which('go')
    if go_exe is None:
        logger.error('go executable not found in PATH')
        return None
    try:
        proc = await asyncio.create_subprocess_exec(go_exe, 'mod', 'vendor', cwd=go_mod_path)
        returncode = await proc.wait()
        if returncode != 0:
            logger.error("Error running 'go mod vendor'.")
            return None
    except OSError:
        logger.exception("Error running 'go mod vendor'.")
        return None

    if lockfile_mode:
        return await build_digest_archive(go_mod_path,
                                          'vendor',
                                          '-vendor.tar.xz',
                                          Path(ebuild).parent.name,
                                          dist_settings=dist_settings,
                                          previous_digest=previous_digest)
    await build_compress(temp_dir,
                         go_mod_path,
                         'vendor',
                         '-vendor.tar.xz',
                         fetchlist,
                         dist_settings=dist_settings)
    return None


def check_gomodule_requirements() -> bool:
    """
    Check if Go is installed.

    Returns
    -------
    bool
        ``True`` if ``go`` is available, otherwise ``False``.
    """
    if not check_program('go', ['version']):
        logger.error('go is not installed')
        return False
    return True
