import xml.etree.ElementTree as etree

from ..settings import LivecheckSettings
from ..utils.portage import get_last_version, catpkg_catpkgsplit
from ..utils import get_content

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
        assert stability is not None
        assert stability.text is not None
        if settings.is_devel(catpkg) or stability.text == 'stable':
            version = release.find(f"{NAMESPACE}v")
            assert version is not None
            assert version.text is not None
            results.append({"tag": version.text})

    if last_version := get_last_version(results, '', ebuild, settings):
        return last_version['version']

    return ''
