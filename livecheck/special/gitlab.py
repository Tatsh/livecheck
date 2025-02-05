from collections.abc import Mapping
from typing import Final
from urllib.parse import quote, urlparse
import re

from ..settings import LivecheckSettings
from ..utils import get_content, is_sha
from ..utils.portage import get_last_version
from .utils import log_unhandled_commit

__all__ = ("get_latest_gitlab_package", "is_gitlab", "GITLAB_METADATA", "get_latest_gitlab",
           "get_latest_gitlab_metadata")

GITLAB_TAG_URL = 'https://%s/api/v4/projects/%s/repository/tags?per_page=%s'
GITLAB_METADATA = 'gitlab'
GITLAB_HOSTNAMES: Final[Mapping[str, str]] = {
    'gitlab': 'gitlab.com',
    'gnome-gitlab': 'gitlab.gnome.org',
    'freedesktop-gitlab': 'gitlab.freedesktop.org'
}

# Number of versions to fetch from GitLab
VERSIONS = 40


def extract_domain_and_namespace(url: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    if not re.search(r"^gitlab\.(com$|.*\.)", parsed.netloc):
        return '', '', ''

    path = parsed.path.strip('/')
    if '/-/' in path:
        path = path.split('/-/')[0]

    return parsed.netloc, path, path.split('/')[-1]


def get_latest_gitlab_package(url: str, ebuild: str,
                              settings: LivecheckSettings) -> tuple[str, str]:

    domain, path_with_namespace, repo = extract_domain_and_namespace(url)
    encoded_path = quote(path_with_namespace, safe='')

    url = GITLAB_TAG_URL % (domain, encoded_path, VERSIONS)

    if not (r := get_content(url)):
        return '', ''

    results: list[dict[str, str]] = [{
        "tag": tag.get("name", ""),
        "id": tag.get("commit", {}).get("id", ""),
    } for tag in r.json()]

    if last_version := get_last_version(results, repo, ebuild, settings):
        return last_version['version'], last_version["id"]

    return '', ''


def get_latest_gitlab(url: str, ebuild: str, settings: LivecheckSettings) -> tuple[str, str, str]:
    last_version = top_hash = hash_date = ''

    if is_sha(urlparse(url).path):
        log_unhandled_commit(ebuild, url)
    else:
        last_version, top_hash = get_latest_gitlab_package(url, ebuild, settings)

    return last_version, top_hash, hash_date


def is_gitlab(url: str) -> bool:
    return bool(extract_domain_and_namespace(url)[0])


def get_latest_gitlab_metadata(remote: str, _type: str, ebuild: str,
                               settings: LivecheckSettings) -> tuple[str, str]:
    uri = GITLAB_HOSTNAMES[_type]
    return get_latest_gitlab_package(f'https://{uri}/{remote}', ebuild, settings)
