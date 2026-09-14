"""GitLab functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, quote, unquote, urlparse
import re

from livecheck.utils import get_content, is_sha
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

from .utils import log_unhandled_commit

if TYPE_CHECKING:
    from collections.abc import Mapping

    from livecheck.settings_model import LivecheckSettings

__all__ = ('GITLAB_METADATA', 'get_latest_gitlab', 'get_latest_gitlab_commit',
           'get_latest_gitlab_metadata', 'get_latest_gitlab_package', 'is_gitlab')

GITLAB_TAG_URL = 'https://%s/api/v4/projects/%s/repository/tags?per_page=%s'
GITLAB_COMMIT_URL = 'https://%s/api/v4/projects/%s/repository/commits?ref_name=%s&per_page=1'
GITLAB_PROJECT_URL = 'https://%s/api/v4/projects/%s'
GITLAB_METADATA = 'gitlab'
_GITLAB_API_PROJECT_RE = re.compile(r'^/api/v4/projects/([^/]+)')
GITLAB_HOSTNAMES: Mapping[str, str] = {
    'freedesktop-gitlab': 'gitlab.freedesktop.org',
    'gitlab': 'gitlab.com',
    'gnome-gitlab': 'gitlab.gnome.org',
    'manjaro-gitlab': 'gitlab.manjaro.org'
}

# Number of versions to fetch from GitLab
VERSIONS = 40


def _gitlab_version_reference(url: str) -> str:
    parts = [part for part in urlparse(url).path.split('/') if part]
    for i, part in enumerate(parts):
        if part == 'archive' and i + 1 < len(parts) and i > 0 and parts[i - 1] == '-':
            return parts[i + 1]
    return ''


def extract_domain_and_namespace(url: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    if not re.search(r'^gitlab\.(com$|.*\.)', parsed.netloc):
        return '', '', ''

    if api_match := _GITLAB_API_PROJECT_RE.match(parsed.path):
        # API URLs carry the namespace as a single URL-encoded path segment.
        path = unquote(api_match.group(1))
    else:
        path = parsed.path.strip('/')
        if '/-/' in path:
            path = path.split('/-/')[0]

    if not path or path.count('/') < 1:
        return '', '', ''

    return parsed.netloc, path, path.split('/')[-1]


def _pinned_sha(url: str) -> str:
    # The commit a URL is pinned to sits in the path on web routes and in the query on API ones.
    parsed = urlparse(url)
    candidates = (parse_qs(parsed.query).get(
        'sha', [''])[0], _gitlab_version_reference(url), parsed.path.rsplit('/', 1)[-1])
    for candidate in candidates:
        # The whole segment has to be the hash. `project-<sha>.tar.bz2` names a commit but is an
        # archive of it, not a reference to it.
        if candidate and is_sha(candidate) == len(candidate):
            return candidate
    return ''


async def _default_branch(domain: str, encoded_path: str) -> str:
    if not (r := await get_content(GITLAB_PROJECT_URL % (domain, encoded_path))):
        return ''
    return str(r.json().get('default_branch', ''))


async def get_latest_gitlab_commit(url: str, branch: str = '') -> tuple[str, str]:
    """
    Get the latest commit hash and date for a GitLab repository.

    Parameters
    ----------
    url : str
        Any project URL in a form understood by :py:func:`extract_domain_and_namespace`.
    branch : str
        Branch name. The project's default branch is used when empty.

    Returns
    -------
    tuple[str, str]
        Commit SHA and ``YYYYMMDD`` date string, or empty strings if the API call fails.
    """
    domain, path_with_namespace, _ = extract_domain_and_namespace(url)
    if not domain:
        return '', ''
    encoded_path = quote(path_with_namespace, safe='')
    if not branch and not (branch := await _default_branch(domain, encoded_path)):
        return '', ''
    if not (r := await get_content(GITLAB_COMMIT_URL %
                                   (domain, encoded_path, quote(branch, safe='')))):
        return '', ''
    if not (commits := r.json()):
        return '', ''
    return str(commits[0].get('id', '')), str(commits[0].get('created_at', ''))[:10].replace(
        '-', '')


async def get_latest_gitlab_package(url: str, ebuild: str,
                                    settings: LivecheckSettings) -> tuple[str, str]:
    """
    Get the latest version of a GitLab package.

    Parameters
    ----------
    url : str
        GitLab project URL.
    ebuild : str
        Ebuild atom string.
    settings : LivecheckSettings
        Livecheck settings.

    Returns
    -------
    tuple[str, str]
        Latest tag version and commit id, or empty strings if unavailable.
    """
    version_reference = _gitlab_version_reference(url)
    domain, path_with_namespace, repo = extract_domain_and_namespace(url)
    encoded_path = quote(path_with_namespace, safe='')

    url = GITLAB_TAG_URL % (domain, encoded_path, VERSIONS)

    if not (r := await get_content(url)):
        return '', ''

    results: list[dict[str, str]] = [{
        'tag': tag.get('name', ''),
        'id': tag.get('commit', {}).get('id', '')
    } for tag in r.json()]

    if last_version := get_last_version(results,
                                        repo,
                                        ebuild,
                                        settings,
                                        version_reference=version_reference):
        return last_version['version'], last_version['id']

    return '', ''


async def get_latest_gitlab(url: str, ebuild: str, settings: LivecheckSettings, *,
                            force_sha: bool) -> tuple[str, str, str]:
    """
    Get the latest version of a GitLab package.

    Parameters
    ----------
    url : str
        GitLab project URL.
    ebuild : str
        Ebuild atom string.
    settings : LivecheckSettings
        Livecheck settings.
    force_sha : bool
        Whether to retain commit hashes when not required.

    Returns
    -------
    tuple[str, str, str]
        Latest version, commit hash, and hash date (date often empty here).
    """
    last_version = top_hash = hash_date = ''

    if _pinned_sha(url):
        # A commit-pinned ebuild has no tag to compare against, so follow the branch instead.
        catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)
        top_hash, hash_date = await get_latest_gitlab_commit(url, settings.branches.get(catpkg, ''))
        if not top_hash:
            log_unhandled_commit(ebuild, url)
    else:
        last_version, top_hash = await get_latest_gitlab_package(url, ebuild, settings)
        if not force_sha:
            top_hash = ''

    return last_version, top_hash, hash_date


def is_gitlab(url: str) -> bool:
    """
    Check if the URL is a GitLab repository.

    Returns
    -------
    bool
        Whether the URL identifies a GitLab repository.
    """
    return bool(extract_domain_and_namespace(url)[0])


async def get_latest_gitlab_metadata(remote: str, _type: str, ebuild: str,
                                     settings: LivecheckSettings) -> tuple[str, str]:
    """
    Get the latest version of a GitLab package from metadata.

    Returns
    -------
    tuple[str, str]
        Latest version string and associated hash or tag information.
    """
    uri = GITLAB_HOSTNAMES[_type]
    return await get_latest_gitlab_package(f'https://{uri}/{remote}', ebuild, settings)
