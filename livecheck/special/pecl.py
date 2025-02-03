import xml.etree.ElementTree as etree

from ..settings import LivecheckSettings
from ..utils import assert_not_none, get_content
from ..utils.portage import catpkg_catpkgsplit, get_last_version

__all__ = ["get_latest_pecl_package"]

PECL_DOWNLOAD_URL = 'https://pecl.php.net/rest/r/%s/allreleases.xml'

NAMESPACE = "{http://pear.php.net/dtd/rest.allreleases}"


def get_latest_pecl_package(ebuild: str, settings: LivecheckSettings) -> str:
    catpkg, _, program_name, _ = catpkg_catpkgsplit(ebuild)

    # Remove 'pecl-' prefix if present
    if program_name.startswith('pecl-'):
        program_name = program_name.replace('pecl-', '', 1)

    url = PECL_DOWNLOAD_URL % (program_name)

    if not (r := get_content(url)):
        return ''

    results = []
    for release in etree.fromstring(r.text).findall(f"{NAMESPACE}r"):
        stability = release.find(f"{NAMESPACE}s")
        stability = assert_not_none(stability)
        if settings.is_devel(catpkg) or assert_not_none(stability.text) == 'stable':
            version = release.find(f"{NAMESPACE}v")
            version = assert_not_none(version)
            results.append({"tag": assert_not_none(version.text)})

    if last_version := get_last_version(results, '', ebuild, settings):
        return last_version['version']

    return ''
