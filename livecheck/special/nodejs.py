"""NodeJS functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
import asyncio
import logging

from livecheck.utils import check_program

from .utils import build_compress, dist_archive_already_uploaded, remove_url_ebuild, search_ebuild

if TYPE_CHECKING:
    from collections.abc import Mapping

    from livecheck.dist_github import DistGitHubSettings

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
                               package_manager: str = 'npm',
                               *,
                               dist_settings: DistGitHubSettings | None = None) -> None:
    """
    Update a NodeJS-based ebuild.

    Parameters
    ----------
    ebuild : str
        Path to the ebuild file.
    path : str | None
        Optional subdirectory path inside the unpacked sources.
    fetchlist : Mapping[str, tuple[str, ...]]
        Fetch map used when compressing the ``node_modules`` output.
    package_manager : str
        Package manager command to use (``npm``, ``pnpm``, or ``yarn``).
    dist_settings : DistGitHubSettings | None
        Optional GitHub release destination for the produced archive.
    """
    if await dist_archive_already_uploaded('-node_modules.tar.xz', fetchlist, dist_settings):
        logger.info('Node modules archive already uploaded; skipping `%s install`.',
                    package_manager.lower())
        return
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

    await build_compress(temp_dir,
                         package_path,
                         'node_modules',
                         '-node_modules.tar.xz',
                         fetchlist,
                         dist_settings=dist_settings)


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
