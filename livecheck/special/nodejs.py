"""NodeJS functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
import logging
import subprocess as sp

from livecheck.utils import check_program

from .utils import build_compress, remove_url_ebuild, search_ebuild

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ('check_nodejs_requirements', 'remove_nodejs_url', 'update_nodejs_ebuild')

logger = logging.getLogger(__name__)


def remove_nodejs_url(ebuild_content: str) -> str:
    """Remove ``node_modules.tar.xz`` line from ebuild."""
    return remove_url_ebuild(ebuild_content, '-node_modules.tar.xz')


def update_nodejs_ebuild(ebuild: str, path: str | None,
                         fetchlist: Mapping[str, tuple[str, ...]]) -> None:
    """Update a NodeJS-based ebuild."""
    package_path, temp_dir = search_ebuild(ebuild, 'package.json', path)
    if not package_path:
        return

    try:
        sp.run(('npm', 'install', '--audit false', '--color false', '--progress false',
                '--ignore-scripts'),
               cwd=package_path,
               check=True)
    except sp.CalledProcessError:
        logger.exception("Error running 'npm install'.")
        return

    build_compress(temp_dir, package_path, 'node_modules', '-node_modules.tar.xz', fetchlist)


def check_nodejs_requirements() -> bool:
    """Check if npm is installed."""
    if not check_program('npm', ['--version']):
        logger.error('npm is not installed')
        return False
    return True
