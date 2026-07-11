"""Github functions."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import quote, urlparse
import re

from livecheck.utils import get_content, is_sha
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

from .utils import get_archive_extension

if TYPE_CHECKING:
    from livecheck.settings_model import LivecheckSettings

__all__ = ('GITHUB_METADATA', 'get_github_branch_for_commit', 'get_latest_github',
           'get_latest_github_commit', 'get_latest_github_commit2', 'get_latest_github_metadata',
           'get_latest_github_package', 'is_github', 'is_github_release_url')

GITHUB_BRANCH_URL = 'https://api.github.com/repos/%s/%s/branches/%s'
GITHUB_COMPARE_URL = 'https://api.github.com/repos/%s/%s/compare/%s...%s'
GITHUB_COMPARE_REACHABLE_STATUSES = frozenset({'ahead', 'identical'})
"""GitHub compare ``status`` values meaning the base commit is reachable from the head ref."""
GITHUB_DATE_URL = 'https://api.github.com/repos/%s/%s/git/refs/tags/%s'
GITHUB_METADATA = 'github'
GITHUB_TAGS_URL = 'https://api.github.com/repos/%s/%s/tags?per_page=100'


def _github_tag_reference(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split('/') if part]
    for i, part in enumerate(parts):
        if part == 'releases' and parts[i:i + 2] == ['releases', 'download']:
            return parts[i + 2] if i + 2 < len(parts) else ''
        if part == 'archive' and i + 1 < len(parts):
            archive_ref = '/'.join(parts[i + 1:])
            archive_ref = re.sub(r'^(?:refs/)?tags/', '', archive_ref)
            if ext := get_archive_extension(archive_ref):
                return archive_ref[:-len(ext)]
            return archive_ref
    if parsed.netloc == 'codeload.github.com' and len(parts) >= 4:  # noqa: PLR2004
        return re.sub(r'^(?:refs/)?tags/', '', '/'.join(parts[3:]))
    return ''


def _github_version_branch_candidates(version: str) -> tuple[str, ...]:
    target_version = re.sub(r'-r\d+$', '', version)
    if not (match := re.match(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?', target_version)):
        return (target_version,)

    parts = [part for part in match.groups() if part]
    # Try the release series (version without the patch level) from most to least specific
    # first, since release branches are usually named after the series rather than the exact
    # version; fall back to the full version last.
    series_parts = parts[:2] if len(parts) > 2 else parts  # noqa: PLR2004
    candidates: list[str] = []
    for length in range(len(series_parts), 0, -1):
        candidate = '.'.join(series_parts[:length])
        candidates.extend((candidate, f'v{candidate}'))
    if len(parts) > 2:  # noqa: PLR2004
        candidate = '.'.join(parts)
        candidates.extend((candidate, f'v{candidate}'))
    return tuple(dict.fromkeys(candidates))


def extract_owner_repo(url: str) -> tuple[str, str, str]:
    u = urlparse(url)
    d = n = u.netloc

    if (m := re.match(r'^([^\.]+)\.github\.(io|com)$', n)):
        p = [x for x in u.path.split('/') if x]
        if not p:
            return '', '', ''
        return f'https://{d}/{p[0]}', m.group(1), p[0]
    # check if uri start with github. and has at least 3 parts
    if (m := re.match(r'^github\.(io|com)$', n)):
        p = [x for x in u.path.split('/') if x]
        if len(p) < 2:  # noqa: PLR2004
            return '', '', ''
        r = p[1].replace('.git', '')
        return f'https://{d}/{p[0]}/{r}', p[0], r
    return '', '', ''


async def get_github_branch_for_commit(url: str, version: str, commit: str) -> str:
    """
    Find a likely GitHub branch containing a version commit.

    Parameters
    ----------
    url : str
        GitHub-related URL.
    version : str
        Ebuild version used to derive branch candidates.
    commit : str
        Commit SHA that must be reachable from the selected branch.

    Returns
    -------
    str
        Branch name containing ``commit``, or an empty string if none is found.
    """
    _, owner, repo = extract_owner_repo(url)
    if not owner or not repo:
        return ''
    for branch in _github_version_branch_candidates(version):
        # Confirm the candidate is a real branch before trusting it. The compare API also
        # resolves tags, so a version such as ``2.10.1`` that exists only as a tag would
        # otherwise be returned as a branch and break ``git-r3`` (it fetches
        # ``refs/heads/<branch>``).
        branch_url = GITHUB_BRANCH_URL % (owner, repo, quote(branch, safe=''))
        if not await get_content(branch_url):
            continue
        compare_url = GITHUB_COMPARE_URL % (owner, repo, quote(commit,
                                                               safe=''), quote(branch, safe=''))
        if not (r := await get_content(compare_url)):
            continue
        if r.json().get('status') in GITHUB_COMPARE_REACHABLE_STATUSES:
            return branch
    return ''


async def get_latest_github_package(url: str, ebuild: str,
                                    settings: LivecheckSettings) -> tuple[str, str]:
    """
    Get the latest version of a Github package.

    Parameters
    ----------
    url : str
        GitHub-related URL (pages, releases, or API-derived domain).
    ebuild : str
        Ebuild atom string.
    settings : LivecheckSettings
        Livecheck settings.

    Returns
    -------
    tuple[str, str]
        Latest tag version and resolved commit SHA, or empty strings if unavailable.
    """
    version_reference = _github_tag_reference(url)
    _, owner, repo = extract_owner_repo(url)
    if not owner or not repo or not (r := await get_content(GITHUB_TAGS_URL % (owner, repo))):
        return '', ''

    try:
        tags = r.json()
    except ValueError:
        return '', ''
    if not isinstance(tags, list):
        return '', ''

    results = [{
        'tag': name,
        'id': name
    } for entry in tags if isinstance(entry, dict) and (name := entry.get('name'))]

    if not (last_version := get_last_version(
            results, repo, ebuild, settings, version_reference=version_reference)):
        return '', ''

    url = GITHUB_DATE_URL % (owner, repo, last_version['id'])
    if not (r := await get_content(url)):
        return last_version['version'], ''

    ref_object = r.json().get('object', {})
    object_url = ref_object.get('url')

    if object_url and ref_object.get('type') == 'tag':
        r2 = await get_content(object_url)
        if not r2:
            return last_version['version'], ''

        tag_data = r2.json()
        sha = tag_data.get('object', {}).get('sha')
    else:
        sha = ref_object.get('sha')

    return last_version['version'], sha or ''


async def get_latest_github_commit(url: str, branch: str) -> tuple[str, str]:
    """
    Get the latest commit hash and date for a Github repository.

    Parameters
    ----------
    url : str
        Repository URL in a form understood by :py:func:`extract_owner_repo`.
    branch : str
        Branch name.

    Returns
    -------
    tuple[str, str]
        Commit SHA and formatted date string, or empty strings if the API call fails.
    """
    _, owner, repo = extract_owner_repo(url)
    if not owner or not repo:
        return '', ''

    return await get_latest_github_commit2(owner, repo, branch)


async def get_latest_github_commit2(owner: str, repo: str, branch: str) -> tuple[str, str]:
    """
    Get the latest commit hash and date for a Github repository.

    Parameters
    ----------
    owner : str
        Repository owner or organisation.
    repo : str
        Repository name.
    branch : str
        Branch name.

    Returns
    -------
    tuple[str, str]
        Commit SHA and formatted date string, or empty strings if the API call fails.
    """
    url = GITHUB_BRANCH_URL % (owner, repo, quote(branch, safe=''))
    if not (r := await get_content(url)):
        return '', ''
    d = r.json()['commit']['commit']['committer']['date'][:10]
    try:
        dt = datetime.fromisoformat(d.replace('Z', '+00:00'))
        formatted_date = dt.strftime('%Y%m%d')
    except ValueError:
        formatted_date = d[:10]
    return r.json()['commit']['sha'], formatted_date


def is_github(url: str) -> bool:
    """
    Check if the URL is a Github repository.

    Parameters
    ----------
    url : str
        URL to inspect.

    Returns
    -------
    bool
        True if :py:func:`extract_owner_repo` yields a non-empty domain.
    """
    return bool(extract_owner_repo(url)[0])


def is_github_release_url(url: str) -> bool:
    """
    Check if the URL is a GitHub releases URL.

    Parameters
    ----------
    url : str
        URL to inspect.

    Returns
    -------
    bool
        True if the URL is a GitHub URL with a ``releases`` path segment.
    """
    return is_github(url) and 'releases' in [part for part in urlparse(url).path.split('/') if part]


def get_branch(url: str, ebuild: str, settings: LivecheckSettings) -> str:
    catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)

    # get branch from url
    parts = url.strip('/').split('/')
    if len(parts) >= 2 and parts[-2] == 'commits':  # noqa: PLR2004
        return parts[-1].replace('.atom', '')

    # get branch from settings
    if (branch := settings.branches.get(catpkg, '')):
        return branch

    # default branch is master
    if is_sha(urlparse(url).path):
        return 'master'

    return ''


async def get_latest_github(url: str, ebuild: str, settings: LivecheckSettings, *,
                            force_sha: bool) -> tuple[str, str, str]:
    """
    Get the latest version of a Github package.

    Parameters
    ----------
    url : str
        GitHub-related URL.
    ebuild : str
        Ebuild atom string.
    settings : LivecheckSettings
        Livecheck settings.
    force_sha : bool
        Whether to retain the commit hash from tag lookups. Hashes from branch lookups are
        always kept because a branch is only resolved for commit-pinned ebuilds.

    Returns
    -------
    tuple[str, str, str]
        Latest version, commit hash, and hash date.
    """
    last_version = top_hash = hash_date = ''

    if (branch := get_branch(url, ebuild, settings)):
        top_hash, hash_date = await get_latest_github_commit(url, branch)
    else:
        last_version, top_hash = await get_latest_github_package(url, ebuild, settings)
        if not force_sha:
            top_hash = ''

    return last_version, top_hash, hash_date


async def get_latest_github_metadata(remote: str, ebuild: str,
                                     settings: LivecheckSettings) -> tuple[str, str]:
    """
    Get the latest version of a Github package from metadata.

    Parameters
    ----------
    remote : str
        ``remote-id`` path from ``metadata.xml``.
    ebuild : str
        Ebuild atom string.
    settings : LivecheckSettings
        Livecheck settings.

    Returns
    -------
    tuple[str, str]
        Latest tag version and commit SHA.
    """
    return await get_latest_github_package(f'https://github.com/{remote}', ebuild, settings)
