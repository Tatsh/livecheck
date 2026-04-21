"""General utilities for special handling."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
import logging
import os
import tarfile
import tempfile

from anyio import Path as AnyioPath, to_thread
from livecheck.utils.portage import get_distdir, unpack_ebuild
from platformdirs import user_cache_dir

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

__all__ = ('EbuildTempFile', 'build_compress', 'get_archive_extension', 'get_project_path',
           'remove_url_ebuild', 'search_ebuild')

logger = logging.getLogger(__name__)


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
        Optional relative directory suffix to match under the temp tree.

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
        if path:
            for root, _, _ in os.walk(temp_dir):
                if root.endswith(path):
                    return root, temp_dir
        else:
            for root, _, files in os.walk(temp_dir):
                if archive in files:
                    return root, temp_dir
        return '', ''

    result = await to_thread.run_sync(_walk_search)
    if result == ('', ''):
        logger.error('Error searching the `%s` inside package.', archive)
    return result


async def build_compress(temp_dir: str, base_dir: str, directory: str, extension: str,
                         fetchlist: Mapping[str, Collection[str]]) -> bool:
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

    Returns
    -------
    bool
        ``True`` if the archive was written, otherwise ``False``.
    """
    vendor_dir = Path(base_dir) / directory
    if not vendor_dir.exists():
        logger.warning('The directory vendor was not created.')
        return False

    if not (filename := next(iter(fetchlist.keys()), None)):
        return False

    if not (archive_ext := get_archive_extension(filename)):
        logger.warning('Invalid extension.')
        return False

    if extension in filename:
        vendor_archive_name = filename
    else:
        base_name = filename[:-len(archive_ext)]
        vendor_archive_name = f'{base_name}{extension}'
    vendor_archive_path = get_distdir() / vendor_archive_name

    vendor_path = Path(base_dir).resolve()
    base_path = Path(temp_dir).resolve()

    relative_path = vendor_path.relative_to(base_path) / directory

    def _compress() -> None:
        with tarfile.open(vendor_archive_path, 'w:xz') as tar:
            tar.add(vendor_dir, arcname=str(relative_path))

    await to_thread.run_sync(_compress)
    return True


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
        name = tempfile.NamedTemporaryFile(  # noqa: SIM115
            mode='w',
            prefix=self._std_ebuild.stem,
            suffix=self._std_ebuild.suffix,
            delete=False,
            dir=str(self._std_ebuild.parent),
            encoding='utf-8').name
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
