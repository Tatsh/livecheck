from urllib.parse import urlparse
import re

from ..settings import LivecheckSettings
from .regex import get_latest_regex_package

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

    last_version, _, _ = get_latest_regex_package(ebuild, url, r'"version":"([^"]+)"[,\}]', '',
                                                  settings)
    return last_version


def is_pypi(url: str) -> bool:
    return bool(extract_project(url))


def get_latest_pypi_metadata(remote: str, ebuild: str, settings: LivecheckSettings) -> str:
    return get_latest_pypi_package2(remote, ebuild, settings)
