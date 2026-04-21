"""Maven functions."""
from __future__ import annotations

from shutil import which
from typing import TYPE_CHECKING
import asyncio
import logging

from livecheck.utils import check_program

from .utils import build_compress, remove_url_ebuild, search_ebuild

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ('check_maven_requirements', 'remove_maven_url', 'update_maven_ebuild')

log = logging.getLogger(__name__)


def remove_maven_url(ebuild_content: str) -> str:
    """
    Remove the URL for the Maven dependency tarball from the ebuild content.

    Returns
    -------
    str
        Ebuild text with the Maven tarball URL line removed.
    """
    return remove_url_ebuild(ebuild_content, '-mvn.tar.xz')


async def update_maven_ebuild(ebuild: str, path: str | None,
                              fetchlist: Mapping[str, tuple[str, ...]]) -> None:
    """Update a Maven package ebuild."""
    maven_path, temp_dir = await search_ebuild(ebuild, 'pom.xml', path)
    if not maven_path:
        return

    mvn_exe = which('mvn')
    if not mvn_exe:
        log.error('mvn is not installed')
        return

    try:
        proc = await asyncio.create_subprocess_exec(mvn_exe,
                                                    '--batch-mode',
                                                    '-Dmaven.repo.local=.m2',
                                                    'dependency:go-offline',
                                                    '-Drat.ignoreErrors=true',
                                                    'package',
                                                    cwd=maven_path)
        returncode = await proc.wait()
        if returncode != 0:
            log.error("Error running 'mvn'.")
            return
    except OSError:
        log.exception("Error running 'mvn'.")
        return

    await build_compress(temp_dir, maven_path, '.m2', '-mvn.tar.xz', fetchlist)


def check_maven_requirements() -> bool:
    """
    Check if Maven is installed.

    Returns
    -------
    bool
        ``True`` if ``mvn`` is available, otherwise ``False``.
    """
    if not check_program('mvn', ['--version']):
        log.error('mvn is not installed')
        return False
    return True
