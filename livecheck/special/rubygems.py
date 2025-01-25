from ..settings import LivecheckSettings
from ..utils.portage import get_last_version
from ..utils import get_content

__all__ = ["get_latest_rubygems_package"]

RUBYGEMS_DOWNLOAD_URL = 'https://rubygems.org/api/v1/versions/%s.json'


def get_latest_rubygems_package(gem_name: str, ebuild: str, development: bool,
                                restrict_version: str, settings: LivecheckSettings) -> str:
    url = RUBYGEMS_DOWNLOAD_URL % (gem_name)

    if not (response := get_content(url)):
        return ''

    results = []
    for release in response.json():
        if development or not release.get("prerelease", False):
            results.append({"tag": release.get("number", "")})

    last_version = get_last_version(results, gem_name, ebuild, development, restrict_version,
                                    settings)
    if last_version:
        return last_version['version']

    return ''
