"""Composer functions."""
from __future__ import annotations

from shutil import which
from typing import TYPE_CHECKING
import asyncio
import logging

from livecheck.utils import check_program

from .utils import build_compress, dist_archive_already_uploaded, remove_url_ebuild, search_ebuild

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
                                 dist_settings: DistGitHubSettings | None = None) -> None:
    """
    Update a Composer package ebuild.

    Parameters
    ----------
    ebuild : str
        Path to the ebuild file.
    path : str | None
        Optional subdirectory path inside the unpacked sources.
    fetchlist : Mapping[str, tuple[str, ...]]
        Fetch map used when compressing vendor output.
    dist_settings : DistGitHubSettings | None
        Optional GitHub release destination for the produced archive.
    """
    if await dist_archive_already_uploaded('-vendor.tar.xz', fetchlist, dist_settings):
        log.info('Vendor archive already uploaded; skipping `composer install`.')
        return
    composer_path, temp_dir = await search_ebuild(ebuild, 'composer.json', path)
    if not composer_path:
        return

    composer_exe = which('composer')
    if composer_exe is None:
        log.error('composer executable not found in PATH')
        return
    try:
        proc = await asyncio.create_subprocess_exec(composer_exe,
                                                    '--no-interaction',
                                                    '--no-scripts',
                                                    'install',
                                                    cwd=composer_path)
        returncode = await proc.wait()
        if returncode != 0:
            log.error("Error running 'composer'.")
            return
    except OSError:
        log.exception("Error running 'composer'.")
        return

    await build_compress(temp_dir,
                         composer_path,
                         'vendor',
                         '-vendor.tar.xz',
                         fetchlist,
                         dist_settings=dist_settings)


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
