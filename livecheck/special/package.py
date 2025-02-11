from urllib.parse import urlparse

from ..settings import LivecheckSettings
from ..utils import get_content
from ..utils.portage import get_last_version

__all__ = ("get_latest_package", "is_package")

PACKAGE_DOWNLOAD_URL = 'https://%s//%s'


def extract_project(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.netloc in ('registry.npmjs.org', 'registry.yarnpkg.com'):
        path = parsed.path
        project = ('/'.join(path.split('/')[1:3]) if path.startswith('/@') else path.split('/')[1])
        return parsed.netloc, project

    return '', ''


def get_latest_package(src_uri: str, ebuild: str, settings: LivecheckSettings) -> str:
    domain, project = extract_project(src_uri)

    url = PACKAGE_DOWNLOAD_URL % (domain, project)

    results: list[dict[str, str]] = []
    if r := get_content(url):
        for release in r.json().get('versions', {}):
            results.extend([{"tag": release}])

        if last_version := get_last_version(results, '', ebuild, settings):
            return last_version['version']

    return ''


def is_package(url: str) -> bool:
    return bool(extract_project(url)[0])
