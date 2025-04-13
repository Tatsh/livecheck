from urllib.parse import urlparse

from livecheck.settings import LivecheckSettings
from livecheck.utils import get_content
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

__all__ = ('RUBYGEMS_METADATA', 'get_latest_rubygems_metadata', 'get_latest_rubygems_package',
           'is_rubygems')

RUBYGEMS_DOWNLOAD_URL = 'https://rubygems.org/api/v1/versions/%s.json'
RUBYGEMS_METADATA = 'rubygems'


def get_latest_rubygems_package(ebuild: str, settings: LivecheckSettings) -> str:
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
    return urlparse(url).netloc == 'rubygems.org'


def get_latest_rubygems_metadata(remote: str, ebuild: str, settings: LivecheckSettings) -> str:
    return get_latest_rubygems_package2(remote, ebuild, settings)
