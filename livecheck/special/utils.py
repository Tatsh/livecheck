"""General utilities for special handling."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
import hashlib
import logging
import os
import re
import stat
import tarfile
import tempfile

from anyio import Path as AnyioPath, to_thread
from platformdirs import user_cache_dir

from livecheck.dist_github import DistGitHubSettings, asset_exists, upload_dist_archive
from livecheck.utils.portage import get_distdir, unpack_ebuild

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Collection, Mapping

__all__ = ('DIGEST_LENGTH', 'EbuildTempFile', 'build_compress', 'build_digest_archive',
           'compute_vendor_archive_name', 'dist_archive_already_uploaded', 'ensure_digest_archive',
           'get_archive_digest', 'get_archive_extension', 'get_project_path', 'remove_url_ebuild',
           'replace_archive_digest', 'search_ebuild')

logger = logging.getLogger(__name__)

DIGEST_LENGTH = 16
"""
Number of hexadecimal digits of the dependency digest in the name of an archive.

:meta hide-value:
"""
_ARCHIVE_DIGEST_RE = re.compile(rf'-([0-9a-f]{{{DIGEST_LENGTH}}})(-[a-z_]+\.tar\.xz)')
_ARCHIVE_NAME_RE = re.compile(r'(?<=/)[^/\s"\']*(-[a-z_]+\.tar\.xz)')


def get_archive_digest(ebuild_content: str, extension: str) -> str | None:
    """
    Find the dependency digest in the name of an archive of an ebuild.

    Parameters
    ----------
    ebuild_content : str
        Full ebuild file text.
    extension : str
        Suffix of the archive name, such as ``-vendor.tar.xz``.

    Returns
    -------
    str | None
        The digest, or ``None`` if the archive is not named after one.
    """
    return next(
        (match.group(1)
         for match in _ARCHIVE_DIGEST_RE.finditer(ebuild_content) if match.group(2) == extension),
        None)


def replace_archive_digest(ebuild_content: str, extension: str, digest: str) -> str:
    """
    Point the URL of an archive of an ebuild to the archive named after a digest.

    Parameters
    ----------
    ebuild_content : str
        Full ebuild file text.
    extension : str
        Suffix of the archive name, such as ``-vendor.tar.xz``.
    digest : str
        Dependency digest returned by the function that built the archive.

    Returns
    -------
    str
        Ebuild text with the archive file name replaced by ``${PN}-<digest><extension>``.
    """
    return _ARCHIVE_NAME_RE.sub(
        lambda match: f'${{PN}}-{digest}{extension}'
        if match.group(1) == extension else match.group(), ebuild_content)


def get_project_path(package_name: str) -> Path:
    """
    Get the project cache path for a given package name.

    Parameters
    ----------
    package_name : str
        Package name used as a subdirectory under the cache root.

    Returns
    -------
    pathlib.Path
        Absolute path to the package cache directory.
    """
    return Path(user_cache_dir('livecheck')) / package_name


def remove_url_ebuild(ebuild: str, remove: str) -> str:
    """
    Remove lines that reference a given URL fragment from ebuild content.

    Parameters
    ----------
    ebuild : str
        Full ebuild file text.
    remove : str
        Substring identifying URLs to strip.

    Returns
    -------
    str
        Ebuild text with matching URL lines removed or shortened.
    """
    lines = ebuild.split('\n')
    filtered_lines = []
    for line in lines:
        original_line = line
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith('#'):
            filtered_lines.append(original_line)
            continue
        if remove in stripped_line and stripped_line.strip(' "\'').endswith(remove):
            if (stripped_line.endswith(('"', "'"))
                    and (stripped_line.count('"') == 1 or stripped_line.count("'") == 1)):
                filtered_lines.append(stripped_line[-1])
            continue
        filtered_lines.append(original_line)
    return '\n'.join(filtered_lines)


async def search_ebuild(ebuild: str, archive: str, path: str | None = None) -> tuple[str, str]:
    """
    Search for an archive file inside an unpacked ebuild tree.

    Parameters
    ----------
    ebuild : str
        Ebuild path or content for :py:func:`~livecheck.utils.portage.unpack_ebuild`.
    archive : str
        Archive filename to locate.
    path : str | None
        Optional suffix that the directory with the archive must end with. Directories that end
        with the suffix but do not have the archive are skipped.

    Returns
    -------
    tuple[str, str]
        Directory containing the archive and temp root path, or empty strings if not found.
    """
    temp_dir = await to_thread.run_sync(lambda: unpack_ebuild(ebuild))
    if not temp_dir:
        logger.warning('Error unpacking the ebuild.')
        return '', ''

    def _walk_search() -> tuple[str, str]:
        for root, _, files in os.walk(temp_dir):
            if archive in files and (not path or root.endswith(path)):
                return root, temp_dir
        return '', ''

    result = await to_thread.run_sync(_walk_search)
    if result == ('', ''):
        logger.error('Error searching the `%s` inside package.', archive)
    return result


def compute_vendor_archive_name(extension: str, fetchlist: Mapping[str, Collection[str]]) -> str:
    """
    Derive the vendor archive filename for an ebuild's fetch map.

    Parameters
    ----------
    extension : str
        Filename suffix to apply when renaming the archive (for example ``-vendor.tar.xz``).
    fetchlist : Mapping[str, Collection[str]]
        Map of upstream filenames to mirror lists.

    Returns
    -------
    str
        Computed filename, or an empty string if no fetch entry or archive extension was found.
    """
    if not (filename := next(iter(fetchlist.keys()), None)):
        return ''
    if not (archive_ext := get_archive_extension(filename)):
        logger.warning('Invalid extension.')
        return ''
    if extension in filename:
        return filename
    return f'{filename[:-len(archive_ext)]}{extension}'


async def dist_archive_already_uploaded(extension: str, fetchlist: Mapping[str, Collection[str]],
                                        dist_settings: DistGitHubSettings | None) -> bool:
    """
    Return whether the vendor archive is already published at the configured GitHub release.

    Parameters
    ----------
    extension : str
        Filename suffix used by the relevant ecosystem (for example ``-vendor.tar.xz``).
    fetchlist : Mapping[str, Collection[str]]
        Map of upstream filenames to mirror lists for the new ebuild.
    dist_settings : DistGitHubSettings | None
        GitHub Releases destination, or ``None`` when uploading is disabled.

    Returns
    -------
    bool
        ``True`` if the asset is already published and the rebuild can be skipped.
    """
    if dist_settings is None or dist_settings.force:
        return False
    if not (name := compute_vendor_archive_name(extension, fetchlist)):
        return False
    return await asset_exists(dist_settings, name)


async def build_compress(temp_dir: str,
                         base_dir: str,
                         directory: str,
                         extension: str,
                         fetchlist: Mapping[str, Collection[str]],
                         *,
                         dist_settings: DistGitHubSettings | None = None) -> bool:
    """
    Build a compressed dist archive from vendor sources.

    Parameters
    ----------
    temp_dir : str
        Temporary build root.
    base_dir : str
        Base directory containing vendor output.
    directory : str
        Vendor subdirectory name under ``base_dir``.
    extension : str
        Filename suffix to apply when renaming the archive.
    fetchlist : Mapping[str, Collection[str]]
        Map of upstream filenames to mirror lists.
    dist_settings : DistGitHubSettings | None
        Optional GitHub Releases destination. When set, the archive is also uploaded as a release
        asset after being written to ``DISTDIR``.

    Returns
    -------
    bool
        ``True`` if the archive was written (and uploaded, when requested), otherwise ``False``.
    """
    vendor_dir = Path(base_dir) / directory
    if not vendor_dir.exists():
        logger.warning('The directory vendor was not created.')
        return False

    if not (vendor_archive_name := compute_vendor_archive_name(extension, fetchlist)):
        return False
    vendor_archive_path = get_distdir() / vendor_archive_name

    vendor_path = Path(str(await AnyioPath(base_dir).resolve()))
    base_path = Path(str(await AnyioPath(temp_dir).resolve()))

    relative_path = vendor_path.relative_to(base_path) / directory

    def _compress() -> None:
        with tarfile.open(vendor_archive_path, 'w:xz') as tar:
            tar.add(vendor_dir, arcname=str(relative_path))

    await to_thread.run_sync(_compress)
    return dist_settings is None or await upload_dist_archive(dist_settings, vendor_archive_path)


async def ensure_digest_archive(package: str,
                                digest: str,
                                extension: str,
                                build: Callable[[Path], Awaitable[bool]],
                                *,
                                dist_settings: DistGitHubSettings | None = None,
                                previous_digest: str | None = None) -> str | None:
    """
    Provide the dependency archive named ``<package>-<digest><extension>``.

    The archive is built only when the previous version does not use it, the GitHub release does
    not publish it, and ``DISTDIR`` does not have it. An archive named after a digest is never
    rebuilt or replaced, even with ``force`` set, as the manifests of the ebuilds that use it record
    its checksum.

    Parameters
    ----------
    package : str
        Package name at the start of the archive name.
    digest : str
        Digest of the dependencies.
    extension : str
        Suffix of the archive name, such as ``-vendor.tar.xz``.
    build : Callable[[Path], Awaitable[bool]]
        Writes the archive at the given temporary path and reports whether it succeeded. The file
        is renamed to the archive name only on success.
    dist_settings : DistGitHubSettings | None
        Optional GitHub release destination for the archive.
    previous_digest : str | None
        Digest of the archive that the previous version uses, if any.

    Returns
    -------
    str | None
        The digest, or ``None`` if the archive could not be built or uploaded.
    """
    archive_name = f'{package}-{digest}{extension}'
    if digest == previous_digest or (dist_settings is not None
                                     and await asset_exists(dist_settings, archive_name)):
        logger.info('The dependencies did not change; reusing `%s`.', archive_name)
        return digest
    archive = get_distdir() / archive_name
    if archive.is_file():
        logger.info('The dependencies did not change; reusing `%s`.', archive_name)
    else:
        # A later run reuses any file with the final name, including one that an interrupted build
        # truncated.
        partial = archive.with_name(f'{archive_name}.partial')
        try:
            if not await build(partial):
                return None
            partial.replace(archive)
        finally:
            partial.unlink(missing_ok=True)
    if dist_settings is not None and not await upload_dist_archive(dist_settings, archive):
        return None
    return digest


def _tree_digest(root: Path, excluded: Callable[[str], bool] | None) -> str:
    entries: list[tuple[str, Path]] = []
    # Path.walk() needs Python 3.12.
    for current, directories, files in os.walk(root):
        for name in (*directories, *files):
            path = Path(current) / name
            entries.append((path.relative_to(root).as_posix(), path))
    digest = hashlib.sha256()
    for relative, path in sorted(entries):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            digest.update(f'l\0{relative}\0{path.readlink()}\0'.encode())
        elif stat.S_ISDIR(mode):
            digest.update(f'd\0{relative}\0'.encode())
        elif stat.S_ISREG(mode) and not (excluded and excluded(path.name)):
            with path.open('rb') as file:
                content = hashlib.file_digest(file, 'sha256').hexdigest()
            executable = 'x' if mode & stat.S_IXUSR else '-'
            digest.update(f'f\0{relative}\0{executable}\0{content}\0'.encode())
    return digest.hexdigest()[:DIGEST_LENGTH]


async def build_digest_archive(base_dir: str,
                               directory: str,
                               extension: str,
                               package: str,
                               *,
                               dist_settings: DistGitHubSettings | None = None,
                               excluded: Callable[[str], bool] | None = None,
                               previous_digest: str | None = None) -> str | None:
    """
    Build a dependency archive named after a digest of the downloaded files.

    The digest covers the paths, contents, executable bits, and symbolic links under the dependency
    directory. Member paths are relative to ``base_dir``, and versions that download the same files
    share the archive. See :py:func:`ensure_digest_archive` for when the archive is built.

    Parameters
    ----------
    base_dir : str
        Directory that the member paths are relative to.
    directory : str
        Dependency directory, relative to ``base_dir``.
    extension : str
        Suffix of the archive name, such as ``-vendor.tar.xz``.
    package : str
        Package name at the start of the archive name.
    dist_settings : DistGitHubSettings | None
        Optional GitHub release destination for the archive.
    excluded : Callable[[str], bool] | None
        Reports whether a file, by its name, is omitted from the digest. The archive still
        includes the file.
    previous_digest : str | None
        Digest of the archive that the previous version uses, if any.

    Returns
    -------
    str | None
        The digest in the name of the archive, or ``None`` on failure.
    """
    vendor_dir = Path(base_dir) / directory
    if not vendor_dir.is_dir():
        logger.warning('The directory vendor was not created.')
        return None
    digest = await to_thread.run_sync(lambda: _tree_digest(vendor_dir, excluded))

    def _compress(archive: Path) -> bool:
        with tarfile.open(archive, 'w:xz') as tar:
            tar.add(vendor_dir, arcname=directory)
        return True

    return await ensure_digest_archive(package,
                                       digest,
                                       extension,
                                       lambda archive: to_thread.run_sync(_compress, archive),
                                       dist_settings=dist_settings,
                                       previous_digest=previous_digest)


def get_archive_extension(filename: str) -> str:
    """
    Detect a known archive extension at the end of a filename.

    Parameters
    ----------
    filename : str
        File or URL basename to inspect.

    Returns
    -------
    str
        Extension including the leading dot, or an empty string if none matched.
    """
    filename = filename.lower()
    for ext in ('gh.tar.gz', 'tar.gz', 'tar.xz', 'tar.bz2', 'tar.lz', 'tar.zst', 'tc.gz', 'tar.z',
                'gz', 'xz', 'zip', 'tbz2', 'bz2', 'tbz', 'txz', 'tar', 'tgz', 'rar', '7z'):
        if filename.endswith(f'.{ext}'):
            return '.' + ext

    return ''


class EbuildTempFile:
    """Ebuild temporary file context manager."""
    def __init__(self, ebuild: str) -> None:
        self.ebuild = AnyioPath(ebuild)
        self._std_ebuild = Path(ebuild)
        self.temp_file: AnyioPath | None = None

    async def __aenter__(self) -> Path:
        """
        Create a temporary file next to the ebuild.

        Returns
        -------
        pathlib.Path
            Path to the writable temporary file.
        """
        fd, name = tempfile.mkstemp(prefix=self._std_ebuild.stem,
                                    suffix=self._std_ebuild.suffix,
                                    dir=str(self._std_ebuild.parent))
        os.close(fd)
        self.temp_file = AnyioPath(name)
        return Path(name)

    async def __aexit__(self, exc_type: object, exc_value: BaseException | None,
                        traceback: object) -> None:
        """Handle the context exit."""
        if exc_type is None:
            if not self.temp_file or not await self.temp_file.exists() or (
                    await self.temp_file.stat()).st_size == 0:
                logger.error('The temporary file is empty or missing.')
                return
            await self.ebuild.unlink(missing_ok=True)
            await self.temp_file.rename(self.ebuild)
            self._std_ebuild.chmod(0o0644)
        if self.temp_file and await self.temp_file.exists():
            await self.temp_file.unlink(missing_ok=True)


def log_unhandled_commit(catpkg: str, src_uri: str) -> None:
    logger.warning('Unhandled commit: %s SRC_URI: %s', catpkg, src_uri)
