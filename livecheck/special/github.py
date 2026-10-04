"""Github functions."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import quote, urlparse
import logging
import re

from livecheck.utils import get_content, is_sha
from livecheck.utils.portage import catpkg_catpkgsplit, current_version_result, get_last_version

from .utils import get_archive_extension

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping

    from livecheck.settings_model import LivecheckSettings

__all__ = ('GITHUB_METADATA', 'get_github_branch_for_commit', 'get_latest_github',
           'get_latest_github_commit', 'get_latest_github_commit2', 'get_latest_github_metadata',
           'get_latest_github_package', 'is_github', 'is_github_release_url')

log = logging.getLogger(__name__)

GITHUB_BRANCH_URL = 'https://api.github.com/repos/%s/%s/branches/%s'
GITHUB_COMMIT_URL = 'https://api.github.com/repos/%s/%s/commits/%s'
GITHUB_COMPARE_URL = 'https://api.github.com/repos/%s/%s/compare/%s...%s'
GITHUB_COMPARE_REACHABLE_STATUSES = frozenset({'ahead', 'identical'})
"""GitHub compare ``status`` values meaning the base commit is reachable from the head ref."""
GITHUB_DATE_URL = 'https://api.github.com/repos/%s/%s/git/refs/tags/%s'
GITHUB_METADATA = 'github'
TAGS_PER_PAGE = 100
"""Number of tags requested per page of the tags API.

:meta hide-value:
"""
GITHUB_TAGS_URL = f'https://api.github.com/repos/%s/%s/tags?per_page={TAGS_PER_PAGE}&page=%d'
STALE_TAG_CHECKS = 5
"""Maximum number of tags whose commit date is checked against the packaged tag per lookup.

:meta hide-value:
"""
TAG_PAGES = 5
"""Maximum number of tag pages fetched while looking for the packaged tag.

:meta hide-value:
"""


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
    if parsed.netloc == 'codeload.github.com' and len(
            parts) >= 4:  # ruff:ignore[magic-value-comparison]
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
    series_parts = parts[:2] if len(parts) > 2 else parts  # ruff:ignore[magic-value-comparison]
    candidates: list[str] = []
    for length in range(len(series_parts), 0, -1):
        candidate = '.'.join(series_parts[:length])
        candidates.extend((candidate, f'v{candidate}'))
    if len(parts) > 2:  # ruff:ignore[magic-value-comparison]
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
        if len(p) < 2:  # ruff:ignore[magic-value-comparison]
            return '', '', ''
        r = p[1].removesuffix('.git')
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


async def _tag_page(owner: str, repo: str, page: int) -> list[dict[str, str]] | None:
    if not (r := await get_content(GITHUB_TAGS_URL % (owner, repo, page))):
        return None
    try:
        tags = r.json()
    except ValueError:
        return None
    if not isinstance(tags, list):
        return None
    results = []
    for entry in tags:
        if not isinstance(entry, dict) or not (name := entry.get('name')):
            continue
        commit = entry.get('commit')
        sha = commit.get('sha', '') if isinstance(commit, dict) else ''
        results.append({'tag': name, 'id': name, 'sha': str(sha or '')})
    return results


async def _tag_results(
        owner: str, repo: str, found: Callable[[Collection[Mapping[str, str]]],
                                               bool]) -> list[dict[str, str]] | None:
    """
    Fetch tags page by page until the wanted one shows up.

    GitHub orders tags by name, so a scheme that sorts first (Go's ``weekly.*`` tags, for example)
    can fill the first page and hide the releases behind it.

    Parameters
    ----------
    owner : str
        Repository owner or organisation.
    repo : str
        Repository name.
    found : Callable[[Collection[Mapping[str, str]]], bool]
        Predicate telling whether the tags fetched so far include the wanted one.

    Returns
    -------
    list[dict[str, str]] | None
        Tag results, or ``None`` if the first page could not be read.
    """
    results: list[dict[str, str]] = []
    for page in range(1, TAG_PAGES + 1):
        if (entries := await _tag_page(owner, repo, page)) is None:
            return results or None
        results.extend(entries)
        if len(entries) < TAGS_PER_PAGE or found(results):
            break
    return results


async def _commit_date(owner: str, repo: str, sha: str) -> str:
    if not sha or not (r := await get_content(GITHUB_COMMIT_URL %
                                              (owner, repo, quote(sha, safe='')))):
        return ''
    try:
        return str(r.json()['commit']['committer']['date'])
    except (KeyError, TypeError, ValueError):
        return ''


async def _newest_tag(results: Collection[Mapping[str, str]],
                      owner: str,
                      repo: str,
                      ebuild: str,
                      settings: LivecheckSettings,
                      version_reference: str = '') -> dict[str, str]:
    """
    Pick the newest tag, ignoring higher tags that predate the packaged one.

    A repository may keep a tag such as ``v1.0.0`` from an abandoned line next to the ``v0.9.x``
    releases it actually ships. Such a tag sorts above the packaged version but its commit is older
    than the packaged tag's commit, so it is dropped and the next candidate is considered.

    Parameters
    ----------
    results : Collection[Mapping[str, str]]
        Tag results as produced by :py:func:`_tag_results`.
    owner : str
        Repository owner or organisation.
    repo : str
        Repository name.
    ebuild : str
        Ebuild atom string.
    settings : LivecheckSettings
        Livecheck settings.
    version_reference : str
        Current upstream tag or filename whose versioned pattern candidates must match.

    Returns
    -------
    dict[str, str]
        Newest acceptable tag result, or an empty dictionary if there is none.
    """
    candidates = list(results)
    current: dict[str, str] | None = None
    current_date = ''
    for _ in range(STALE_TAG_CHECKS):
        if not (last_version := get_last_version(
                candidates, repo, ebuild, settings, version_reference=version_reference)):
            return {}
        if not last_version.get('sha'):
            return last_version
        if current is None:
            current = current_version_result(results, repo, ebuild, settings) or {}
        if (not current.get('sha') or current['tag'] == last_version['tag']
                or not (current_date := current_date
                        or await _commit_date(owner, repo, current['sha']))):
            return last_version
        candidate_date = await _commit_date(owner, repo, last_version['sha'])
        if not candidate_date or candidate_date >= current_date:
            return last_version
        log.debug('Skip tag `%s` (%s): older than the packaged tag `%s` (%s).', last_version['tag'],
                  candidate_date, current['tag'], current_date)
        candidates = [result for result in candidates if result['tag'] != last_version['tag']]
    log.debug('Gave up on %s after %d tags older than the packaged tag.', ebuild, STALE_TAG_CHECKS)
    return {}


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
    if not owner or not repo or (results := await _tag_results(
            owner, repo,
            lambda fetched: current_version_result(fetched, repo, ebuild, settings) is not None)
                                 ) is None:
        return '', ''

    if not (last_version := await _newest_tag(
            results, owner, repo, ebuild, settings, version_reference=version_reference)):
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
        dt = datetime.fromisoformat(d)
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


def _explicit_branch(url: str, ebuild: str, settings: LivecheckSettings) -> str:
    catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)

    # get branch from url
    parts = url.strip('/').split('/')
    if len(parts) >= 2 and parts[-2] == 'commits':  # ruff:ignore[magic-value-comparison]
        return parts[-1].replace('.atom', '')

    # get branch from settings
    return str(settings.branches.get(catpkg, ''))


def get_branch(url: str, ebuild: str, settings: LivecheckSettings) -> str:
    if (branch := _explicit_branch(url, ebuild, settings)):
        return branch

    # default branch is master
    if is_sha(urlparse(url).path):
        return 'master'

    return ''


def _pinned_sha(url: str) -> str:
    if not (length := is_sha(urlparse(url).path)):
        return ''
    return urlparse(url).path.rsplit('/', 1)[-1][:length]


async def _latest_from_pinned_tag(url: str, ebuild: str,
                                  settings: LivecheckSettings) -> tuple[str, str, str] | None:
    """
    Resolve a commit-pinned URL through the tag list when the commit is a release tag.

    An ebuild that pins the commit of a release tag (for example a ROCm ``therock-10.0`` commit
    from a monorepo archive) tracks releases, not the default branch, so the branch head must not
    trigger a revision bump on every run.

    Parameters
    ----------
    url : str
        GitHub URL whose last path segment is the pinned commit.
    ebuild : str
        Ebuild atom string.
    settings : LivecheckSettings
        Livecheck settings.

    Returns
    -------
    tuple[str, str, str] | None
        Latest version, its commit, and an empty date, or ``None`` if the commit is not a tag.
    """
    sha = _pinned_sha(url)
    _, owner, repo = extract_owner_repo(url)

    def is_pinned(result: Mapping[str, str]) -> bool:
        return result['sha'].startswith(sha)

    if not owner or not repo or (results := await _tag_results(
            owner, repo, lambda fetched: any(is_pinned(result) for result in fetched))) is None:
        return None
    if not (pinned := [result for result in results if is_pinned(result)]):
        return None
    # Several tags may sit on the same commit, so the one carrying the highest version names the
    # release line the ebuild follows.
    if not (pinned_tag := get_last_version(pinned, repo, ebuild, settings)):
        return None
    log.debug('Commit %s is tag `%s`; comparing tags instead of a branch.', sha, pinned_tag['tag'])
    _, _, _, ebuild_version = catpkg_catpkgsplit(ebuild)
    if (last_version := await _newest_tag(
            results, owner, repo, ebuild, settings,
            version_reference=pinned_tag['tag'])) and last_version['tag'] != pinned_tag['tag']:
        return last_version['version'], last_version['sha'], ''
    return ebuild_version, '', ''


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

    if (_pinned_sha(url) and not _explicit_branch(url, ebuild, settings)
            and (pinned := await _latest_from_pinned_tag(url, ebuild, settings)) is not None):
        return pinned
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
