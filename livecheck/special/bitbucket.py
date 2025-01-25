import re

from ..settings import LivecheckSettings
from ..utils.portage import get_last_version
from ..utils import get_content, is_compressed_file

__all__ = ("get_latest_bitbucket_package",)

# doc: https://developer.atlassian.com/cloud/bitbucket/rest/api-group-refs/#api-repositories-workspace-repo-slug-refs-tags-get
BITBUCKET_TAG_URL = 'https://api.bitbucket.org/2.0/repositories/%s/%s/refs/tags'

# doc: https://developer.atlassian.com/cloud/bitbucket/rest/api-group-downloads/#api-repositories-workspace-repo-slug-downloads-get
BITBUCKET_DOWNLOAD_URL = 'https://api.bitbucket.org/2.0/repositories/%s/%s/downloads'

MAX_ITERATIONS = 4


def get_latest_bitbucket_package(path: str, ebuild: str, development: bool, restrict_version: str,
                                 settings: LivecheckSettings) -> tuple[str, str]:
    workspace, repository = path.strip("/").split('/')[:2]

    url = BITBUCKET_TAG_URL % (workspace, repository)

    if not (tags_response := get_content(url)):
        return '', ''

    results: list[dict[str, str]] = []
    for tag in tags_response.json().get("values", []):
        results.append({
            "tag": tag.get("name", ""),
            "id": tag.get("target", {}).get("hash", ""),
        })

    # The tag may not be created and you need to know the downloads
    # for the latest versions
    url = BITBUCKET_DOWNLOAD_URL % (workspace, repository)
    iteration_count = 0

    while url and iteration_count < MAX_ITERATIONS:
        if not (response := get_content(url)):
            break
        data = response.json()

        for item in data.get("values", []):
            if is_compressed_file(item.get('name',)):
                results.append({
                    "tag": item.get('name', ''),
                    "id": '',
                })

        url = data.get('next')
        iteration_count += 1

    last_version = get_last_version(results, repository, ebuild, development, restrict_version,
                                    settings)
    if last_version:
        return last_version['version'], last_version["id"]

    return '', ''
