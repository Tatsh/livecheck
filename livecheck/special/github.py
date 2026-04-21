"""Github functions."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse
import re

from defusedxml import ElementTree as ET  # noqa: N817
from livecheck.constants import RSS_NS
from livecheck.utils import get_content, is_sha
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

if TYPE_CHECKING:
    from livecheck.settings_model import LivecheckSettings

__all__ = ('GITHUB_METADATA', 'get_latest_github', 'get_latest_github_commit',
           'get_latest_github_commit2', 'get_latest_github_metadata', 'get_latest_github_package',
           'is_github')

GITHUB_DOWNLOAD_URL = '%s/tags.atom'
GITHUB_COMMIT_URL = 'https://api.github.com/repos/%s/%s/branches/%s'
GITHUB_DATE_URL = 'https://api.github.com/repos/%s/%s/git/refs/tags/%s'
GITHUB_METADATA = 'github'


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
    domain, owner, repo = extract_owner_repo(url)
    url = GITHUB_DOWNLOAD_URL % (domain)
    if not owner or not repo or not (r := await get_content(url)):
        return '', ''

    try:
        root = ET.fromstring(r.text or '')
    except ET.ParseError:
        return '', ''

    results: list[dict[str, str]] = []
    for tag_id_element in root.findall('entry/id', RSS_NS):
        tag_id = tag_id_element.text

        tag = tag_id.split('/')[-1] if tag_id and '/' in tag_id else ''
        if tag := (tag_id.split('/')[-1] if tag_id and '/' in tag_id else ''):
            results.append({'tag': tag, 'id': tag})

    if not (last_version := get_last_version(results, repo, ebuild, settings)):
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
    url = GITHUB_COMMIT_URL % (owner, repo, branch)
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
        Whether to retain commit hashes when not required.

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
