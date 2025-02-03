from ..settings import LivecheckSettings
from ..utils import get_content
from ..utils.portage import catpkg_catpkgsplit, get_last_version

__all__ = ["get_latest_rubygems_package"]

RUBYGEMS_DOWNLOAD_URL = 'https://rubygems.org/api/v1/versions/%s.json'


def get_latest_rubygems_package(ebuild: str, settings: LivecheckSettings) -> str:
    catpkg, _, gem_name, _ = catpkg_catpkgsplit(ebuild)

    url = RUBYGEMS_DOWNLOAD_URL % (gem_name)

    if not (response := get_content(url)):
        return ''

    results = []
    for release in response.json():
        if settings.is_devel(catpkg) or not release.get("prerelease", False):
            results.append({"tag": release.get("number", "")})

    if last_version := get_last_version(results, gem_name, ebuild, settings):
        return last_version['version']

    return ''
