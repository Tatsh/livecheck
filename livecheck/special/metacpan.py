"""MetaCPAN functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse
import re

from livecheck.utils import get_content
from livecheck.utils.portage import get_last_version

if TYPE_CHECKING:
    from livecheck.settings import LivecheckSettings

__all__ = ('METACPAN_METADATA', 'get_latest_metacpan_metadata', 'get_latest_metacpan_package',
           'is_metacpan')

METACPAN_METADATA = 'cpan'
METACPAN_DOWNLOAD_URL1 = 'https://fastapi.metacpan.org/v1/release/_search?q=distribution:%s'
METACPAN_DOWNLOAD_URL2 = 'https://fastapi.metacpan.org/v1/release/%s'


def extract_perl_package(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc not in {'metacpan.org', 'cpan'}:
        return ''

    match = re.search(r'/([^/]+)-[\d.]+\.*', parsed.path)
    return match.group(1) if match else ''


def get_latest_metacpan_package(url: str, ebuild: str, settings: LivecheckSettings) -> str:
    """Get the latest version of a MetaCPAN package."""
    package_name = extract_perl_package(url)
    return get_latest_metacpan_package2(package_name, ebuild, settings)


def get_latest_metacpan_package2(package_name: str, ebuild: str,
                                 settings: LivecheckSettings) -> str:
    results: list[dict[str, str]] = []
    url = METACPAN_DOWNLOAD_URL1 % (package_name)
    if r := get_content(url):
        for hit in r.json().get('hits', {}).get('hits', []):
            results.extend([{'tag': hit['_source']['version']}])

    # Many times it does not exist as in the previous list,
    # that is why the latest version is checked again.
    url = METACPAN_DOWNLOAD_URL2 % (package_name)
    if r := get_content(url):
        results.append({'tag': r.json().get('version')})

    last_version = get_last_version(results, package_name, ebuild, settings)
    if last_version:
        return last_version['version']

    return ''


def is_metacpan(url: str) -> bool:
    """Check if the URL is a MetaCPAN URL."""
    return bool(extract_perl_package(url))


def get_latest_metacpan_metadata(remote: str, ebuild: str, settings: LivecheckSettings) -> str:
    """Get the latest version of a MetaCPAN package."""
    return get_latest_metacpan_package2(remote, ebuild, settings)
