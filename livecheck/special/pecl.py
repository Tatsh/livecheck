"""PECL functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse
import re

from defusedxml import ElementTree as ET  # ruff:ignore[camelcase-imported-as-acronym]

from livecheck.utils import assert_not_none, get_content
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

if TYPE_CHECKING:
    from livecheck.settings_model import LivecheckSettings

__all__ = ('PECL_METADATA', 'get_latest_pecl_metadata', 'get_latest_pecl_package', 'is_pecl')

PECL_DOWNLOAD_URL = 'https://pecl.php.net/rest/r/%s/allreleases.xml'

PECL_METADATA = 'pecl'

NAMESPACE = '{http://pear.php.net/dtd/rest.allreleases}'
_DOWNLOAD_PACKAGE = re.compile(r'/get/([^/]+?)-\d[^/]*$')


async def get_latest_pecl_package(ebuild: str,
                                  settings: LivecheckSettings,
                                  src_uri: str = '') -> str:
    """
    Get the latest version of a PECL package.

    Parameters
    ----------
    ebuild : str
        Ebuild atom used for version filtering and fallback package identification.
    settings : LivecheckSettings
        Package update settings.
    src_uri : str
        PECL download URL used to identify upstream package names. Defaults to an empty string.

    Returns
    -------
    str
        Latest PECL version string, or an empty string if none.
    """
    _, _, program_name, _ = catpkg_catpkgsplit(ebuild)

    if match := _DOWNLOAD_PACKAGE.search(urlparse(src_uri).path):
        program_name = match.group(1)
    else:
        program_name = program_name.removeprefix('pecl-')
    return await get_latest_pecl_package2(program_name, ebuild, settings)


async def get_latest_pecl_package2(program_name: str, ebuild: str,
                                   settings: LivecheckSettings) -> str:
    catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)

    url = PECL_DOWNLOAD_URL % (program_name)

    if not (r := await get_content(url)):
        return ''

    results: list[dict[str, str]] = []
    for release in ET.fromstring(r.text or '').findall(f'{NAMESPACE}r'):
        stability = release.find(f'{NAMESPACE}s')
        stability = assert_not_none(stability)
        if settings.is_devel(catpkg) or assert_not_none(stability.text) == 'stable':
            version = release.find(f'{NAMESPACE}v')
            version = assert_not_none(version)
            results.append({'tag': assert_not_none(version.text)})

    if last_version := get_last_version(results, '', ebuild, settings):
        return last_version['version']

    return ''


def is_pecl(url: str) -> bool:
    """
    Check if the URL is a PECL URL.

    Returns
    -------
    bool
        Whether the host is ``pecl.php.net``.
    """
    return urlparse(url).netloc == 'pecl.php.net'


async def get_latest_pecl_metadata(remote: str, ebuild: str, settings: LivecheckSettings) -> str:
    """
    Get the latest version of a PECL package.

    Returns
    -------
    str
        Latest version string from metadata lookup, or an empty string if none.
    """
    return await get_latest_pecl_package2(remote, ebuild, settings)
