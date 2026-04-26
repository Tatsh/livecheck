"""NodeJS functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
import asyncio
import logging

from livecheck.utils import check_program

from .utils import build_compress, remove_url_ebuild, search_ebuild

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ('check_nodejs_requirements', 'remove_nodejs_url', 'update_nodejs_ebuild')

logger = logging.getLogger(__name__)

PACKAGE_MANAGER_COMMANDS: dict[str, tuple[str, ...]] = {
    'npm': ('npm', 'install', '--ignore-scripts', '--no-audit', '--no-color', '--no-progress'),
    'yarn': ('yarn', 'install', '--silent'),
    'pnpm': ('pnpm', 'install', '--ignore-scripts', '--silent')
}


def remove_nodejs_url(ebuild_content: str) -> str:
    """
    Remove ``node_modules.tar.xz`` line from ebuild.

    Returns
    -------
    str
        Ebuild text with the Node modules archive URL line removed.
    """
    return remove_url_ebuild(ebuild_content, '-node_modules.tar.xz')


async def update_nodejs_ebuild(ebuild: str,
                               path: str | None,
                               fetchlist: Mapping[str, tuple[str, ...]],
                               package_manager: str = 'npm') -> None:
    """Update a NodeJS-based ebuild."""
    package_path, temp_dir = await search_ebuild(ebuild, 'package.json', path)
    if not package_path:
        return

    manager = package_manager.lower()
    command = PACKAGE_MANAGER_COMMANDS.get(manager)
    if not command:
        logger.error('Unsupported package manager: %s', package_manager)
        return

    try:
        proc = await asyncio.create_subprocess_exec(*command, cwd=package_path)
        returncode = await proc.wait()
        if returncode != 0:
            logger.error("Error running '%s install'.", manager)
            return
    except OSError:
        logger.exception("Error running '%s install'.", manager)
        return

    await build_compress(temp_dir, package_path, 'node_modules', '-node_modules.tar.xz', fetchlist)


def check_nodejs_requirements(package_manager: str = 'npm') -> bool:
    """
    Check if the requested package manager is installed.

    Returns
    -------
    bool
        ``True`` if the package manager executable is available, otherwise ``False``.
    """
    manager = package_manager.lower()
    command = PACKAGE_MANAGER_COMMANDS.get(manager)
    if not command:
        logger.error('Unsupported package manager: %s', package_manager)
        return False

    if not check_program(command[0], ['--version']):
        logger.error('%s is not installed', command[0])
        return False
    return True
