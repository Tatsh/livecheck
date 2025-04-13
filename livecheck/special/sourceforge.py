from pathlib import Path
from urllib.parse import urlparse
import re
import xml.etree.ElementTree as ET

from livecheck.settings import LivecheckSettings
from livecheck.utils import get_content
from livecheck.utils.portage import get_last_version

from .utils import get_archive_extension

__all__ = ('SOURCEFORGE_METADATA', 'get_latest_sourceforge_metadata',
           'get_latest_sourceforge_package', 'is_sourceforge')

SOURCEFORGE_DOWNLOAD_URL = 'https://sourceforge.net/projects/%s/rss'
SOURCEFORGE_METADATA = 'sourceforge'


def extract_repository(url: str) -> str:
    parsed = urlparse(url)
    n = parsed.netloc
    if n in {'downloads.sourceforge.net', 'download.sourceforge.net', 'sf.net'}:
        path = parsed.path.split('/')
        if 'projects' in path[1] or 'project' in path[1]:
            return path[2]
        return path[1]

    if (m := re.match(r'^([^\.]+)\.(sf|sourceforge)\.(net|io|jp)$', n)):
        return m.group(1)

    return ''


def get_latest_sourceforge_package(src_uri: str, ebuild: str, settings: LivecheckSettings) -> str:
    repository = extract_repository(src_uri)
    return get_latest_sourceforge_package2(repository, ebuild, settings)


def get_latest_sourceforge_package2(repository: str, ebuild: str,
                                    settings: LivecheckSettings) -> str:
    url = SOURCEFORGE_DOWNLOAD_URL % (repository)

    if not (r := get_content(url)):
        return ''

    results: list[dict[str, str]] = []
    for item in ET.fromstring(r.text).findall('.//item'):
        title = item.find('title')
        version = Path(title.text).name if title is not None and title.text else ''
        if version and get_archive_extension(version):
            results.append({'tag': version})

    if last_version := get_last_version(results, repository, ebuild, settings):
        return last_version['version']

    return ''


def is_sourceforge(url: str) -> bool:
    return bool(extract_repository(url))


def get_latest_sourceforge_metadata(remote: str, ebuild: str, settings: LivecheckSettings) -> str:
    return get_latest_sourceforge_package2(remote, ebuild, settings)
