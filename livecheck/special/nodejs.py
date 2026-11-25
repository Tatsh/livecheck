"""NodeJS functions."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal
import asyncio
import hashlib
import logging
import os
import posixpath
import tarfile

from anyio import to_thread

from livecheck.dist_github import upload_dist_archive
from livecheck.utils import check_program
from livecheck.utils.portage import get_distdir

from .utils import (
    DIGEST_LENGTH,
    compute_vendor_archive_name,
    dist_archive_already_uploaded,
    ensure_digest_archive,
    remove_url_ebuild,
    search_ebuild,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from livecheck.dist_github import DistGitHubSettings

__all__ = ('check_nodejs_requirements', 'remove_nodejs_url', 'update_nodejs_ebuild')

logger = logging.getLogger(__name__)

PACKAGE_MANAGER_COMMANDS: dict[str, tuple[str, ...]] = {
    'npm': ('npm', 'install', '--ignore-scripts', '--no-audit', '--no-color', '--no-progress'),
    'yarn': ('yarn', 'install', '--silent'),
    'pnpm': ('pnpm', 'install', '--ignore-scripts', '--silent')
}
PACKAGE_MANAGER_OMIT_DEV_FLAGS: dict[str, tuple[str, ...]] = {
    'npm': ('--omit=dev',),
    'yarn': ('--production',),
    'pnpm': ('--prod',)
}
_ARCHIVE_EXTENSION = '-node_modules.tar.xz'
# Settings files that change the node_modules layout of an install, besides the lockfiles.
_CONFIG_FILES = ('.npmrc', '.yarnrc', '.yarnrc.yml', 'pnpm-workspace.yaml')
_LOCKFILES = ('npm-shrinkwrap.json', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock')


class _ExternalSymlinkError(Exception):
    """Raised when a ``node_modules`` tree has a link that points out of the archive."""


def remove_nodejs_url(ebuild_content: str) -> str:
    """
    Remove ``node_modules.tar.xz`` line from ebuild.

    Returns
    -------
    str
        Ebuild text with the Node modules archive URL line removed.
    """
    return remove_url_ebuild(ebuild_content, _ARCHIVE_EXTENSION)


def _dependency_digest(directories: Sequence[tuple[str, Path]], manager: str, *,
                       omit_dev: bool) -> str | None:
    digest = hashlib.sha256(f'{manager}\0{omit_dev}\0'.encode())
    for name, directory in directories:
        if not any((directory / lockfile).is_file() for lockfile in _LOCKFILES):
            logger.error('There is no lockfile in `%s`.', directory)
            return None
        for file_name in sorted((*_CONFIG_FILES, *_LOCKFILES)):
            if (file := directory / file_name).is_file():
                digest.update(f'{name}/{file_name}\0'.encode())
                digest.update(file.read_bytes())
                digest.update(b'\0')
    return digest.hexdigest()[:DIGEST_LENGTH]


def _find_node_modules(root: Path) -> frozenset[Path]:
    found: set[Path] = set()
    # Path.walk() needs Python 3.12.
    for current, directories, _ in os.walk(root):
        if 'node_modules' in directories:
            found.add(Path(current) / 'node_modules')
        directories[:] = [name for name in directories if name not in {'.git', 'node_modules'}]
    return frozenset(found)


def _reject_external_links(member: tarfile.TarInfo) -> tarfile.TarInfo:
    if member.issym():
        target = posixpath.normpath(posixpath.join(posixpath.dirname(member.name), member.linkname))
        if posixpath.isabs(member.linkname) or target == '..' or target.startswith('../'):
            raise _ExternalSymlinkError(member.name, member.linkname)
    return member


def _write_archive(archive: Path, root: Path, directories: Iterable[Path]) -> bool:
    external_link: tuple[str, ...] = ()
    try:
        with tarfile.open(archive, 'w:xz') as tar:
            for directory in directories:
                tar.add(directory,
                        arcname=str(directory.relative_to(root)),
                        filter=_reject_external_links)
    except _ExternalSymlinkError as e:
        external_link = e.args
    if not external_link:
        return True
    # A link out of the tree, such as one into the global store of pnpm, would be dangling
    # wherever the archive is unpacked.
    archive.unlink(missing_ok=True)
    logger.error('`%s` links to `%s` outside of the archive.', *external_link)
    return False


async def _install(manager: str, directory: Path, *, omit_dev: bool) -> bool:
    command = list(PACKAGE_MANAGER_COMMANDS[manager])
    env = None
    if manager == 'pnpm':
        # Outside of CI, pnpm and the pnpmfile hooks of some projects link the dependencies from
        # a store shared by the user instead of the project directory.
        has_lockfile = (directory / 'pnpm-lock.yaml').is_file()
        command.append('--frozen-lockfile' if has_lockfile else '--no-frozen-lockfile')
        env = {**os.environ, 'CI': 'true'}
    if omit_dev:
        command.extend(PACKAGE_MANAGER_OMIT_DEV_FLAGS[manager])
    try:
        proc = await asyncio.create_subprocess_exec(*command, cwd=directory, env=env)
        returncode = await proc.wait()
    except OSError:
        logger.exception("Error running '%s install'.", manager)
        return False
    if returncode != 0:
        logger.error("Error running '%s install'.", manager)
        return False
    return True


async def _archive_installs(manager: str, directories: Sequence[tuple[str, Path]], archive: Path,
                            archive_root: Path, *, omit_dev: bool) -> bool:
    root = directories[0][1]
    existing = await to_thread.run_sync(_find_node_modules, root)
    for _, directory in directories:
        if not await _install(manager, directory, omit_dev=omit_dev):
            return False
    found = await to_thread.run_sync(_find_node_modules, root)
    archived = found - existing
    if (root_modules := root / 'node_modules') in found:
        archived |= {root_modules}
    if not archived:
        logger.warning('The directory vendor was not created.')
        return False
    paths = sorted(archived)
    return await to_thread.run_sync(lambda: _write_archive(archive, archive_root, paths))


async def update_nodejs_ebuild(
    ebuild: str,
    path: str | None,
    fetchlist: Mapping[str, tuple[str, ...]],
    package_manager: str = 'npm',
    *,
    archive_mode: Literal['lockfile', 'version'] = 'version',
    dist_settings: DistGitHubSettings | None = None,
    omit_dev: bool = False,
    previous_digest: str | None = None,
    workspaces: Sequence[str] = ()) -> str | None:
    """
    Update a NodeJS-based ebuild.

    The ``node_modules`` directories created by the installs in the main package directory and in
    the workspaces go into a single archive. In ``lockfile`` mode the archive is named after a
    digest of the lockfiles and the package manager settings, and its member paths are relative to
    the directory of the main ``package.json``. Versions with the same dependencies share the
    archive, and the install is skipped when the archive exists. See
    :py:func:`~livecheck.special.utils.ensure_digest_archive` for when the archive is built.

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
    archive_mode : Literal['lockfile', 'version']
        Whether the archive is named after the package version or after the lockfile digest.
    dist_settings : DistGitHubSettings | None
        Optional GitHub release destination for the produced archive.
    omit_dev : bool
        Install only the runtime dependencies, leaving the development ones out of the
        archive. Only use it for ebuilds that do not run a build step.
    previous_digest : str | None
        Lockfile digest of the archive that the previous version uses, if any.
    workspaces : Sequence[str]
        Further install directories, relative to the directory of the main ``package.json``.

    Returns
    -------
    str | None
        In ``lockfile`` mode, the digest in the name of the archive for the ebuild. ``None`` in
        ``version`` mode and on failure.
    """
    lockfile_mode = archive_mode == 'lockfile'
    if not lockfile_mode and await dist_archive_already_uploaded(_ARCHIVE_EXTENSION, fetchlist,
                                                                 dist_settings):
        logger.info('Node modules archive already uploaded; skipping `%s install`.',
                    package_manager.lower())
        return None
    package_path, temp_dir = await search_ebuild(ebuild, 'package.json', path)
    if not package_path:
        return None

    manager = package_manager.lower()
    if manager not in PACKAGE_MANAGER_COMMANDS:
        logger.error('Unsupported package manager: %s', package_manager)
        return None

    root = Path(package_path)
    directories = (('.', root), *((workspace, root / workspace) for workspace in workspaces))
    for workspace, directory in directories[1:]:
        if not (directory / 'package.json').is_file():
            logger.error('There is no `package.json` in the workspace `%s`.', workspace)
            return None

    if lockfile_mode:
        if not (digest := await to_thread.run_sync(
                lambda: _dependency_digest(directories, manager, omit_dev=omit_dev))):
            return None
        return await ensure_digest_archive(
            Path(ebuild).parent.name,
            digest,
            _ARCHIVE_EXTENSION,
            lambda archive: _archive_installs(
                manager, directories, archive, root, omit_dev=omit_dev),
            dist_settings=dist_settings,
            previous_digest=previous_digest)
    if not (archive_name := compute_vendor_archive_name(_ARCHIVE_EXTENSION, fetchlist)):
        return None
    archive = get_distdir() / archive_name
    if (await _archive_installs(manager, directories, archive, Path(temp_dir), omit_dev=omit_dev)
            and dist_settings is not None):
        await upload_dist_archive(dist_settings, archive)
    return None


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
