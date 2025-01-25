import xml.etree.ElementTree as etree

from ..settings import LivecheckSettings
from ..utils.portage import get_last_version
from ..utils import get_content

__all__ = ["get_latest_pecl_package"]

PECL_DOWNLOAD_URL = 'https://pecl.php.net/rest/r/%s/allreleases.xml'

NAMESPACE = "{http://pear.php.net/dtd/rest.allreleases}"


def get_latest_pecl_package(program_name: str, ebuild: str, development: bool,
                            restrict_version: str, settings: LivecheckSettings) -> str:
    # Remove 'pecl-' prefix if present
    if program_name.startswith('pecl-'):
        program_name = program_name.replace('pecl-', '', 1)

    url = PECL_DOWNLOAD_URL % (program_name)

    if not (r := get_content(url)):
        return ''

    results = []
    for release in etree.fromstring(r.text).findall(f"{NAMESPACE}r"):
        stability = release.find(f"{NAMESPACE}s")
        stability = stability.text if stability is not None else ""
        if development or stability == 'stable':
            version = release.find(f"{NAMESPACE}v")
            version = version.text if version is not None else ""
            results.append({"tag": version})

    if last_version := get_last_version(results, '', ebuild, development, restrict_version,
                                        settings):
        return last_version['version']

    return ''
