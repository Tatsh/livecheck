"""PyPI functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse
import re

from livecheck.utils import get_content
from livecheck.utils.portage import get_last_version

from .utils import get_archive_extension

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from livecheck.settings import LivecheckSettings

__all__ = ('PYPI_METADATA', 'get_latest_pypi_metadata', 'get_latest_pypi_package', 'is_pypi')

PYPI_METADATA = 'pypi'

PYPI_DOWNLOAD_URL = 'https://pypi.org/pypi/%s/json'


def extract_project(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.split('/')
    if (parsed.netloc in {'pypi', 'pypi.org', 'pypi.io', 'files.pythonhosted.org'}
            and len(path) > 3):  # noqa: PLR2004
        if path[2] == 'source':
            return path[4]
        if m := re.search(r'^(.*?)(?=-\d)', path[-1]):
            return m.group(1).strip()

    return ''


def get_url(ext: str, item: Collection[Mapping[str, str]]) -> str:
    for urls in item:
        if urls['url'].endswith(ext):
            return urls['url']
    for urls in item:
        if get_archive_extension(urls['url']):
            return str(urls['url'])
    return ''


def get_latest_pypi_package(src_uri: str, ebuild: str,
                            settings: LivecheckSettings) -> tuple[str, str]:
    """Get the latest version of a PyPI package."""
    project_name = extract_project(src_uri)
    return get_latest_pypi_package2(project_name, src_uri, ebuild, settings)


def get_latest_pypi_package2(project_name: str, src_uri: str, ebuild: str,
                             settings: LivecheckSettings) -> tuple[str, str]:
    url = PYPI_DOWNLOAD_URL % (project_name)
    ext = get_archive_extension(src_uri)

    results: list[dict[str, str]] = []
    if r := get_content(url):
        for release, item in r.json().get('releases', {}).items():
            results.extend([{'tag': release, 'url': get_url(ext, item)}])

        if last_version := get_last_version(results, '', ebuild, settings):
            return last_version['version'], last_version['url']

    return '', ''


def is_pypi(url: str) -> bool:
    """Check if the URL is a PyPI URL."""
    return bool(extract_project(url))


def get_latest_pypi_metadata(remote: str, ebuild: str,
                             settings: LivecheckSettings) -> tuple[str, str]:
    """Get the latest version of a PyPI package."""
    return get_latest_pypi_package2(remote, '', ebuild, settings)
