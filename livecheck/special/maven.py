"""Maven functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
import logging
import subprocess as sp

from livecheck.utils import check_program

from .utils import build_compress, remove_url_ebuild, search_ebuild

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ('check_maven_requirements', 'remove_maven_url', 'update_maven_ebuild')

log = logging.getLogger(__name__)


def remove_maven_url(ebuild_content: str) -> str:
    """Remove the URL for the Maven dependency tarball from the ebuild content."""
    return remove_url_ebuild(ebuild_content, '-mvn.tar.xz')


def update_maven_ebuild(ebuild: str, path: str | None, fetchlist: Mapping[str, tuple[str,
                                                                                     ...]]) -> None:
    """Update a Maven package ebuild."""
    maven_path, temp_dir = search_ebuild(ebuild, 'pom.xml', path)
    if not maven_path:
        return

    try:
        sp.run(('mvn', '--batch-mode', '-Dmaven.repo.local=.m2', 'dependency:go-offline',
                '-Drat.ignoreErrors=true', 'package'),
               cwd=maven_path,
               check=True)
    except sp.CalledProcessError:
        log.exception("Error running 'mvn'.")
        return

    build_compress(temp_dir, maven_path, '.m2', '-mvn.tar.xz', fetchlist)


def check_maven_requirements() -> bool:
    """Check if Maven is installed."""
    if not check_program('mvn', ['--version']):
        log.error('mvn is not installed')
        return False
    return True
