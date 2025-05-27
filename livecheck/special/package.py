"""NPM functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from livecheck.utils import get_content
from livecheck.utils.portage import get_last_version

if TYPE_CHECKING:
    from livecheck.settings import LivecheckSettings

__all__ = ('get_latest_package', 'is_package')

PACKAGE_DOWNLOAD_URL = 'https://%s//%s'


def extract_project(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.netloc in {'registry.npmjs.org', 'registry.yarnpkg.com'
                         } and (project :=
                                ('/'.join(parsed.path.split('/')[1:3])
                                 if parsed.path.startswith('/@') else parsed.path.split('/')[1])):
        return parsed.netloc, project

    return '', ''


def get_latest_package(src_uri: str, ebuild: str, settings: LivecheckSettings) -> str:
    """Get the latest version of an NPM package."""
    domain, project = extract_project(src_uri)

    url = PACKAGE_DOWNLOAD_URL % (domain, project)

    results: list[dict[str, str]] = []
    if r := get_content(url):
        for release in r.json().get('versions', {}):
            results.extend([{'tag': release}])

        if last_version := get_last_version(results, '', ebuild, settings):
            return last_version['version']

    return ''


def is_package(url: str) -> bool:
    """Check if the URL is an NPM package URL."""
    return bool(extract_project(url)[0])
