from urllib.parse import urlparse
import re

from ..settings import LivecheckSettings
from ..utils import get_content
from ..utils.portage import get_last_version

__all__ = ("get_latest_pypi_package", "is_pypi", "PYPI_METADATA", "get_latest_pypi_metadata")

PYPI_METADATA = 'pypi'

PYPI_DOWNLOAD_URL = 'https://pypi.org/pypi/%s/json'


def extract_project(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.split('/')
    if parsed.netloc in ('pypi', 'pypi.org', 'pypi.io', 'files.pythonhosted.org') and len(path) > 3:
        if path[2] == 'source':
            return path[4]
        if m := re.search(r'(.*)[-_]?[0-9][0-9\._-].*', path[-1]):
            return m.group(1).strip()

    return ''


def get_latest_pypi_package(src_uri: str, ebuild: str, settings: LivecheckSettings) -> str:
    project_name = extract_project(src_uri)
    return get_latest_pypi_package2(project_name, ebuild, settings)


def get_latest_pypi_package2(project_name: str, ebuild: str, settings: LivecheckSettings) -> str:
    url = PYPI_DOWNLOAD_URL % (project_name)

    results: list[dict[str, str]] = []
    if r := get_content(url):
        for release in r.json().get("releases", {}):
            results.extend([{"tag": release}])

        if last_version := get_last_version(results, '', ebuild, settings):
            return last_version['version']

    return ''


def is_pypi(url: str) -> bool:
    return bool(extract_project(url))


def get_latest_pypi_metadata(remote: str, ebuild: str, settings: LivecheckSettings) -> str:
    return get_latest_pypi_package2(remote, ebuild, settings)
