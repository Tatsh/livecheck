"""Composer functions."""
from __future__ import annotations

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
    """Remove the URL for the vendor tarball from the ebuild content."""
    return remove_url_ebuild(ebuild_content, '-vendor.tar.xz')


def update_composer_ebuild(ebuild: str, path: str | None,
                           fetchlist: Mapping[str, tuple[str, ...]]) -> None:
    """Update a Composer package ebuild."""
    composer_path, temp_dir = search_ebuild(ebuild, 'composer.json', path)
    if not composer_path:
        return

    try:
        sp.run(('composer', '--no-interaction', '--no-scripts', 'install'),
               cwd=composer_path,
               check=True)
    except sp.CalledProcessError:
        log.exception("Error running 'composer'.")
        return

    build_compress(temp_dir, composer_path, 'vendor', '-vendor.tar.xz', fetchlist)


def check_composer_requirements() -> bool:
    """Check if Composer is installed."""
    if not check_program('composer', ['--version']):
        log.error('composer is not installed')
        return False
    return True
