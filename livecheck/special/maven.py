"""Maven functions."""
from __future__ import annotations

from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING, Literal
import asyncio
import logging

from livecheck.utils import check_program

from .utils import (
    build_compress,
    build_digest_archive,
    dist_archive_already_uploaded,
    remove_url_ebuild,
    search_ebuild,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from livecheck.dist_github import DistGitHubSettings

__all__ = ('check_maven_requirements', 'remove_maven_url', 'update_maven_ebuild')

log = logging.getLogger(__name__)

# Maven Resolver writes these records with the time of each download, and they differ between runs
# that download the same artifacts.
_RESOLVER_RECORDS = frozenset({'_remote.repositories', 'resolver-status.properties'})


def _is_resolver_record(name: str) -> bool:
    return (name in _RESOLVER_RECORDS or name.endswith('.lastUpdated')
            or name.startswith('maven-metadata-'))


def remove_maven_url(ebuild_content: str) -> str:
    """
    Remove the URL for the Maven dependency tarball from the ebuild content.

    Returns
    -------
    str
        Ebuild text with the Maven tarball URL line removed.
    """
    return remove_url_ebuild(ebuild_content, '-mvn.tar.xz')


async def update_maven_ebuild(ebuild: str,
                              path: str | None,
                              fetchlist: Mapping[str, tuple[str, ...]],
                              *,
                              archive_mode: Literal['lockfile', 'version'] = 'version',
                              dist_settings: DistGitHubSettings | None = None,
                              previous_digest: str | None = None) -> str | None:
    """
    Update a Maven package ebuild.

    In ``lockfile`` mode the archive is named after a digest of the downloaded artifacts, and its
    member paths are relative to the directory of ``pom.xml``. The download records of Maven
    Resolver (``_remote.repositories``, ``*.lastUpdated``, ``maven-metadata-*``, and
    ``resolver-status.properties``) are omitted from the digest.

    Parameters
    ----------
    ebuild : str
        Path to the ebuild file.
    path : str | None
        Optional subdirectory path inside the unpacked sources.
    fetchlist : Mapping[str, tuple[str, ...]]
        Fetch map used when compressing the Maven repository output.
    archive_mode : Literal['lockfile', 'version']
        Whether the archive is named after the package version or after the dependency digest.
    dist_settings : DistGitHubSettings | None
        Optional GitHub release destination for the produced archive.
    previous_digest : str | None
        Dependency digest of the archive that the previous version uses, if any.

    Returns
    -------
    str | None
        In ``lockfile`` mode, the digest in the name of the archive for the ebuild. ``None`` in
        ``version`` mode and on failure.
    """
    lockfile_mode = archive_mode == 'lockfile'
    if not lockfile_mode and await dist_archive_already_uploaded('-mvn.tar.xz', fetchlist,
                                                                 dist_settings):
        log.info('Maven archive already uploaded; skipping `mvn` run.')
        return None
    maven_path, temp_dir = await search_ebuild(ebuild, 'pom.xml', path)
    if not maven_path:
        return None

    mvn_exe = which('mvn')
    if not mvn_exe:
        log.error('mvn is not installed')
        return None

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
            return None
    except OSError:
        log.exception("Error running 'mvn'.")
        return None

    if lockfile_mode:
        return await build_digest_archive(maven_path,
                                          '.m2',
                                          '-mvn.tar.xz',
                                          Path(ebuild).parent.name,
                                          dist_settings=dist_settings,
                                          excluded=_is_resolver_record,
                                          previous_digest=previous_digest)
    await build_compress(temp_dir,
                         maven_path,
                         '.m2',
                         '-mvn.tar.xz',
                         fetchlist,
                         dist_settings=dist_settings)
    return None


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
