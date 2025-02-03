import os
import re
import xml.etree.ElementTree as etree
from urllib.parse import urlparse

from ..settings import LivecheckSettings
from ..utils.portage import get_last_version
from ..utils import get_content
from .utils import get_archive_extension

__all__ = ("get_latest_sourceforge_package", "is_sourceforge")

SOURCEFORGE_DOWNLOAD_URL = 'https://sourceforge.net/projects/%s/rss'


def extract_repository(url: str) -> str:
    parsed = urlparse(url)
    n = parsed.netloc
    if n in {'downloads.sourceforge.net', 'download.sourceforge.net', 'sf.net'}:
        if '/projects/' in parsed.path or '/project/' in parsed.path:
            return parsed.path.split('/')[2]
        return parsed.path.split('/')[1]

    if (m := re.match(r'^([^\.]+)\.(sf|sourceforge)\.(net|io|jp)$', n)):
        return m.group(1)

    return ''


def get_latest_sourceforge_package(src_uri: str, ebuild: str, settings: LivecheckSettings) -> str:
    repository = extract_repository(src_uri)
    url = SOURCEFORGE_DOWNLOAD_URL % (repository)

    if not (r := get_content(url)):
        return ''

    results = []

    for item in etree.fromstring(r.text).findall(".//item"):
        title = item.find("title")
        version = os.path.basename(title.text) if title is not None and title.text else ''
        if version and get_archive_extension(version):
            results.append({"tag": version})

    if last_version := get_last_version(results, repository, ebuild, settings):
        return last_version['version']

    return ''


def is_sourceforge(url: str) -> bool:
    return bool(extract_repository(url))
