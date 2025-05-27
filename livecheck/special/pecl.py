"""PECL functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from defusedxml import ElementTree as ET  # noqa: N817
from livecheck.utils import assert_not_none, get_content
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

if TYPE_CHECKING:
    from livecheck.settings import LivecheckSettings

__all__ = ('PECL_METADATA', 'get_latest_pecl_metadata', 'get_latest_pecl_package', 'is_pecl')

PECL_DOWNLOAD_URL = 'https://pecl.php.net/rest/r/%s/allreleases.xml'

PECL_METADATA = 'pecl'

NAMESPACE = '{http://pear.php.net/dtd/rest.allreleases}'


def get_latest_pecl_package(ebuild: str, settings: LivecheckSettings) -> str:
    """Get the latest version of a PECL package."""
    _, _, program_name, _ = catpkg_catpkgsplit(ebuild)

    # Remove 'pecl-' prefix if present
    if program_name.startswith('pecl-'):
        program_name = program_name.replace('pecl-', '', 1)
    return get_latest_pecl_package2(program_name, ebuild, settings)


def get_latest_pecl_package2(program_name: str, ebuild: str, settings: LivecheckSettings) -> str:
    catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)

    url = PECL_DOWNLOAD_URL % (program_name)

    if not (r := get_content(url)):
        return ''

    results: list[dict[str, str]] = []
    for release in ET.fromstring(r.text).findall(f'{NAMESPACE}r'):
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
    """Check if the URL is a PECL URL."""
    return urlparse(url).netloc == 'pecl.php.net'


def get_latest_pecl_metadata(remote: str, ebuild: str, settings: LivecheckSettings) -> str:
    """Get the latest version of a PECL package."""
    return get_latest_pecl_package2(remote, ebuild, settings)
