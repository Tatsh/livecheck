"""Golang (go-module) utilities."""
from __future__ import annotations

from shutil import which
from typing import TYPE_CHECKING
import logging
import subprocess as sp

from livecheck.utils import check_program

from .utils import build_compress, remove_url_ebuild, search_ebuild

if TYPE_CHECKING:
    from collections.abc import Mapping

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


def update_gomodule_ebuild(ebuild: str, path: str | None,
                           fetchlist: Mapping[str, tuple[str, ...]]) -> None:
    """
    Update a Go module-based ebuild.

    Parameters
    ----------
    ebuild : str
        Path to the ebuild file.
    path : str | None
        Optional subdirectory path inside the unpacked sources.
    fetchlist : Mapping[str, tuple[str, ...]]
        Fetch map used when compressing vendor output.
    """
    go_mod_path, temp_dir = search_ebuild(ebuild, 'go.mod', path)
    if not go_mod_path:
        return

    go_exe = which('go')
    if go_exe is None:
        logger.error('go executable not found in PATH')
        return
    try:
        sp.run((go_exe, 'mod', 'vendor'), cwd=go_mod_path, check=True)
    except sp.CalledProcessError:
        logger.exception("Error running 'go mod vendor'.")
        return

    build_compress(temp_dir, go_mod_path, 'vendor', '-vendor.tar.xz', fetchlist)


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
