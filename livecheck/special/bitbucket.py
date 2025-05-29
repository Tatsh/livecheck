"""Bitbucket functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from livecheck.utils import get_content, is_sha
from livecheck.utils.portage import get_last_version

from .utils import get_archive_extension, log_unhandled_commit

if TYPE_CHECKING:
    from livecheck.settings import LivecheckSettings

__all__ = ('BITBUCKET_METADATA', 'get_latest_bitbucket', 'get_latest_bitbucket_metadata',
           'get_latest_bitbucket_package', 'is_bitbucket')

# doc: https://developer.atlassian.com/cloud/bitbucket/rest/api-group-refs/#api-repositories-workspace-repo-slug-refs-tags-get
BITBUCKET_TAG_URL = 'https://api.bitbucket.org/2.0/repositories/%s/%s/refs/tags'
# doc: https://developer.atlassian.com/cloud/bitbucket/rest/api-group-downloads/#api-repositories-workspace-repo-slug-downloads-get
BITBUCKET_DOWNLOAD_URL = 'https://api.bitbucket.org/2.0/repositories/%s/%s/downloads'
BITBUCKET_METADATA = 'bitbucket'
MAX_ITERATIONS = 4


def extract_workspace_and_repository(url: str) -> tuple[str, str]:
    parsed = urlparse(url)

    if (parsed.netloc != 'bitbucket.org'
            or len(parsed.path.strip('/').split('/')) < 2):  # noqa: PLR2004
        return '', ''

    workspace, repository = parsed.path.strip('/').split('/')[:2]

    return workspace, repository.replace('.git', '')


def get_latest_bitbucket_package(url: str, cpv: str,
                                 settings: LivecheckSettings) -> tuple[str, str]:
    """Get the latest version of a Bitbucket package."""
    workspace, repository = extract_workspace_and_repository(url)

    url = BITBUCKET_TAG_URL % (workspace, repository)

    if not (tags_response := get_content(url)):
        return '', ''

    results: list[dict[str, str]] = [{
        'tag': tag.get('name', ''),
        'id': tag.get('target', {}).get('hash', '')
    } for tag in tags_response.json().get('values', [])]

    # The tag may not be created and you need to know the downloads
    # for the latest versions
    url = BITBUCKET_DOWNLOAD_URL % (workspace, repository)
    iteration_count = 0

    while url and iteration_count < MAX_ITERATIONS:
        if not (r := get_content(url)).ok:
            break
        data = r.json()

        results.extend({
            'tag': item.get('name', ''),
            'id': ''
        } for item in data.get('values', []) if get_archive_extension(item.get('name')))

        url = data.get('next')
        iteration_count += 1

    if last_version := get_last_version(results, repository, cpv, settings):
        return last_version['version'], last_version['id']

    return '', ''


def get_latest_bitbucket(url: str, cpv: str, settings: LivecheckSettings, *,
                         force_sha: bool) -> tuple[str, str, str]:
    """Get the latest version of a Bitbucket package."""
    last_version = top_hash = hash_date = ''

    if is_sha(urlparse(url).path):
        log_unhandled_commit(cpv, url)
    else:
        last_version, top_hash = get_latest_bitbucket_package(url, cpv, settings)
        if not force_sha:
            top_hash = ''

    return last_version, top_hash, hash_date


def is_bitbucket(url: str) -> bool:
    """Check if the URL is a Bitbucket repository."""
    return bool(extract_workspace_and_repository(url)[0])


def get_latest_bitbucket_metadata(remote: str, cpv: str,
                                  settings: LivecheckSettings) -> tuple[str, str]:
    """Get the latest version of a Bitbucket package from metadata."""
    return get_latest_bitbucket_package(f'https://bitbucket.org/{remote}', cpv, settings)
