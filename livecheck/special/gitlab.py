import re
from urllib.parse import urlparse, quote

from ..settings import LivecheckSettings
from ..utils.portage import get_last_version
from ..utils import get_content

__all__ = ("get_latest_gitlab_package",)

GITLAB_TAG_URL = 'https://%s/api/v4/projects/%s/repository/tags?per_page=%s'

# Number of versions to fetch from GitLab
VERSIONS = 40


def extract_domain_and_namespace(url: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    if '/-/' in path:
        path = path.split('/-/')[0]

    return parsed.netloc, path, path.split('/')[-1]


def get_latest_gitlab_package(url: str, ebuild: str, development: bool, restrict_version: str,
                              settings: LivecheckSettings) -> tuple[str, str]:

    domain, path_with_namespace, repo = extract_domain_and_namespace(url)
    encoded_path = quote(path_with_namespace, safe='')

    url = GITLAB_TAG_URL % (domain, encoded_path, VERSIONS)

    if not (tags_response := get_content(url)):
        return '', ''

    results: list[dict[str, str]] = []
    for tag in tags_response.json():
        results.append({
            "tag": tag.get("name", ""),
            "id": tag.get("commit", {}).get("id", ""),
        })

    if last_version := get_last_version(results, repo, ebuild, development, restrict_version,
                                        settings):
        return last_version['version'], last_version["id"]

    return '', ''
