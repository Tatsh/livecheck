"""SourceHut utility functions."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse
import re

from defusedxml import ElementTree as ET  # noqa: N817
from livecheck.utils import get_content, is_sha
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

if TYPE_CHECKING:
    from livecheck.settings import LivecheckSettings

__all__ = ('SOURCEHUT_METADATA', 'get_latest_sourcehut', 'get_latest_sourcehut_commit',
           'get_latest_sourcehut_metadata', 'get_latest_sourcehut_package', 'is_sourcehut')

SOURCEHUT_DOWNLOAD_URL = 'https://%s/%s/%s/refs/rss.xml'
SOURCEHUT_COMMIT_URL = 'https://%s/%s/%s/log/%s/rss.xml'
SOURCEHUT_METADATA = 'sourcehut'


def extract_owner_repo(url: str) -> tuple[str, str, str]:
    if m := re.match(
            r'^(https?://)?(?P<d>(?:(?:git|hg)\.)?sr\.ht)/(?P<u>~?[^/]+)/(?P<p>[^/]+)(/.*)?', url):
        return m.group('d'), m.group('u'), m.group('p')
    return '', '', ''


def get_latest_sourcehut_package(url: str, ebuild: str, settings: LivecheckSettings) -> str:
    """Get the latest version of a SourceHut package."""
    domain, owner, repo = extract_owner_repo(url)
    if not owner or not repo:
        return ''

    url = SOURCEHUT_DOWNLOAD_URL % (domain, owner, repo)

    if not (r := get_content(url)):
        return ''

    results: list[dict[str, str]] = []
    for item in ET.fromstring(r.text).findall('channel/item'):
        guid = item.find('guid')
        if version := guid.text.split('/')[-1] if guid is not None and guid.text else '':
            results.append({'tag': version})

    if last_version := get_last_version(results, repo, ebuild, settings):
        return last_version['version']
    return ''


def get_latest_sourcehut_commit(url: str, branch: str = 'master') -> tuple[str, str]:
    """Get the latest commit hash and date from a SourceHut repository."""
    domain, owner, repo = extract_owner_repo(url)
    if not owner or not repo:
        return '', ''

    url = SOURCEHUT_COMMIT_URL % (domain, owner, repo, branch)

    if not (r := get_content(url)):
        return '', ''

    guid = ET.fromstring(r.text).find('channel/item/guid')
    pubdate = ET.fromstring(r.text).find('channel/item/pubDate')
    commit = guid.text.split('/')[-1] if guid is not None and guid.text else ''
    date = pubdate.text if pubdate is not None and pubdate.text else ''

    try:
        dt = datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %z')
        formatted_date = dt.strftime('%Y%m%d')
    except ValueError:
        formatted_date = ''
    return commit, formatted_date


def is_sourcehut(url: str) -> bool:
    """Check if the given URL is a SourceHut repository."""
    return bool(extract_owner_repo(url)[0])


def get_branch(url: str, ebuild: str, settings: LivecheckSettings) -> str:
    catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)

    # get branch from url
    parts = url.strip('/').split('/')
    if len(parts) >= 3 and parts[-3] == 'log':  # noqa: PLR2004
        return parts[-2]

    # get branch from settings
    if branch := settings.branches.get(catpkg, ''):
        return branch

    # default branch is master
    if is_sha(urlparse(url).path):
        return 'master'

    return ''


def get_latest_sourcehut(url: str, ebuild: str, settings: LivecheckSettings, *,
                         force_sha: bool) -> tuple[str, str, str]:
    """Get the latest version and commit hash from a SourceHut repository."""
    last_version = top_hash = hash_date = ''

    if (branch := get_branch(url, ebuild, settings)):
        top_hash, hash_date = get_latest_sourcehut_commit(url, branch)
        if not force_sha:
            top_hash = ''
    else:
        last_version = get_latest_sourcehut_package(url, ebuild, settings)

    return last_version, top_hash, hash_date


def get_latest_sourcehut_metadata(remote: str, ebuild: str, settings: LivecheckSettings) -> str:
    """Get the latest version of a SourceHut package from its metadata."""
    if not (last_version := get_latest_sourcehut_package(f'https://git.sr.ht/{remote}', ebuild,
                                                         settings)):
        last_version = get_latest_sourcehut_package(f'https://hg.sr.ht/{remote}', ebuild, settings)

    return last_version
