"""RubyGems functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from livecheck.utils import get_content
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

if TYPE_CHECKING:
    from livecheck.settings import LivecheckSettings

__all__ = ('RUBYGEMS_METADATA', 'get_latest_rubygems_metadata', 'get_latest_rubygems_package',
           'is_rubygems')

RUBYGEMS_DOWNLOAD_URL = 'https://rubygems.org/api/v1/versions/%s.json'
RUBYGEMS_METADATA = 'rubygems'


def get_latest_rubygems_package(ebuild: str, settings: LivecheckSettings) -> str:
    """Get the latest version of a RubyGems package."""
    _, _, gem_name, _ = catpkg_catpkgsplit(ebuild)
    return get_latest_rubygems_package2(gem_name, ebuild, settings)


def get_latest_rubygems_package2(gem_name: str, ebuild: str, settings: LivecheckSettings) -> str:
    catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)
    url = RUBYGEMS_DOWNLOAD_URL % (gem_name)

    if not (response := get_content(url)):
        return ''

    results: list[dict[str, str]] = [
        {
            'tag': release.get('number', '')
        } for release in response.json()
        if settings.is_devel(catpkg) or not release.get('prerelease', False)
    ]

    if last_version := get_last_version(results, gem_name, ebuild, settings):
        return last_version['version']

    return ''


def is_rubygems(url: str) -> bool:
    """Check if the URL is a RubyGems URL."""
    return urlparse(url).netloc == 'rubygems.org'


def get_latest_rubygems_metadata(remote: str, ebuild: str, settings: LivecheckSettings) -> str:
    """Get the latest version of a RubyGems package."""
    return get_latest_rubygems_package2(remote, ebuild, settings)
