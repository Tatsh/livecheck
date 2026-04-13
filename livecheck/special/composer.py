"""Composer functions."""
from __future__ import annotations

from shutil import which
from typing import TYPE_CHECKING
import logging
import subprocess as sp

from livecheck.utils import check_program

from .utils import build_compress, remove_url_ebuild, search_ebuild

if TYPE_CHECKING:
    from collections.abc import Mapping

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


def update_composer_ebuild(ebuild: str, path: str | None,
                           fetchlist: Mapping[str, tuple[str, ...]]) -> None:
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
    """
    composer_path, temp_dir = search_ebuild(ebuild, 'composer.json', path)
    if not composer_path:
        return

    composer_exe = which('composer')
    if composer_exe is None:
        log.error('composer executable not found in PATH')
        return
    try:
        sp.run((composer_exe, '--no-interaction', '--no-scripts', 'install'),
               cwd=composer_path,
               check=True)
    except sp.CalledProcessError:
        log.exception("Error running 'composer'.")
        return

    build_compress(temp_dir, composer_path, 'vendor', '-vendor.tar.xz', fetchlist)


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
