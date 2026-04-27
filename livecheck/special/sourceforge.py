"""SourceForge utility functions."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse
import re

from defusedxml import ElementTree as ET  # noqa: N817
from livecheck.utils import get_content
from livecheck.utils.portage import get_last_version

from .utils import get_archive_extension

if TYPE_CHECKING:
    from livecheck.settings_model import LivecheckSettings

__all__ = ('SOURCEFORGE_METADATA', 'get_latest_sourceforge_metadata',
           'get_latest_sourceforge_package', 'is_sourceforge')

SOURCEFORGE_DOWNLOAD_URL = 'https://sourceforge.net/projects/%s/rss'
SOURCEFORGE_METADATA = 'sourceforge'


def _sourceforge_version_reference(url: str) -> str:
    parts = [part for part in urlparse(url).path.split('/') if part]
    if parts and parts[-1] == 'download':
        return parts[-2] if len(parts) > 1 else ''
    return Path(urlparse(url).path).name


def extract_repository(url: str) -> str:
    parsed = urlparse(url)
    n = parsed.netloc
    if n in {'downloads.sourceforge.net', 'download.sourceforge.net', 'sf.net'}:
        path = parsed.path.split('/')
        if 'projects' in path[1] or 'project' in path[1]:
            return path[2]
        return path[1]

    if (m := re.match(r'^([^\.]+)\.(sf|sourceforge)\.(net|io|jp)$', n)):
        return m.group(1)

    return ''


async def get_latest_sourceforge_package(src_uri: str, ebuild: str,
                                         settings: LivecheckSettings) -> str:
    """
    Get the latest version of a SourceForge package.

    Returns
    -------
    str
        Latest release filename version from the RSS feed, or an empty string if none.
    """
    repository = extract_repository(src_uri)
    return await get_latest_sourceforge_package2(
        repository, ebuild, settings, version_reference=_sourceforge_version_reference(src_uri))


async def get_latest_sourceforge_package2(repository: str,
                                          ebuild: str,
                                          settings: LivecheckSettings,
                                          version_reference: str = '') -> str:
    url = SOURCEFORGE_DOWNLOAD_URL % (repository)

    if not (r := await get_content(url)):
        return ''

    results: list[dict[str, str]] = []
    for item in ET.fromstring(r.text or '').findall('.//item'):
        title = item.find('title')
        version = Path(title.text).name if title is not None and title.text else ''
        if version and get_archive_extension(version):
            results.append({'tag': version})

    if last_version := get_last_version(results,
                                        repository,
                                        ebuild,
                                        settings,
                                        version_reference=version_reference):
        return last_version['version']

    return ''


def is_sourceforge(url: str) -> bool:
    """
    Check whether the URL refers to a SourceForge repository.

    Parameters
    ----------
    url : str
        URL to inspect.

    Returns
    -------
    bool
        ``True`` if a SourceForge project slug can be extracted, otherwise ``False``.
    """
    return bool(extract_repository(url))


async def get_latest_sourceforge_metadata(remote: str, ebuild: str,
                                          settings: LivecheckSettings) -> str:
    """
    Get the latest version of a SourceForge package using metadata.

    Parameters
    ----------
    remote : str
        SourceForge project slug from ebuild metadata.
    ebuild : str
        Ebuild content or path context for version selection.
    settings : LivecheckSettings
        Livecheck configuration.

    Returns
    -------
    str
        Latest release version from the RSS feed, or an empty string if none.
    """
    return await get_latest_sourceforge_package2(remote, ebuild, settings)
