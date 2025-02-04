from datetime import datetime
from urllib.parse import urlparse
import re
import xml.etree.ElementTree as etree

from ..constants import RSS_NS
from ..settings import LivecheckSettings
from ..utils import get_content, is_sha
from ..utils.portage import catpkg_catpkgsplit, get_last_version

__all__ = ("get_latest_github_package", "get_latest_github_commit", "get_latest_github_commit2",
           "is_github", "get_latest_github", "GITHUB_METADATA")

GITHUB_DOWNLOAD_URL = '%s/tags.atom'
GITHUB_COMMIT_URL = 'https://api.github.com/repos/%s/%s/branches/%s'
GITHUB_DATE_URL = 'https://api.github.com/repos/%s/%s/git/refs/tags/%s'
GITHUB_METADATA = 'github'


def extract_owner_repo(url: str) -> tuple[str, str, str]:
    u = urlparse(url)
    d = n = u.netloc
    m = re.match(r'^([^\.]+)\.github\.(io|com)$', n)
    if m:
        p = [x for x in u.path.split('/') if x]
        if not p:
            return '', '', ''
        return f"https://{d}/{p[0]}", m.group(1), p[0]
    if 'github.' in n:
        p = [x for x in u.path.split('/') if x]
        if len(p) < 2:
            return '', '', ''
        r = p[1].replace('.git', '')
        return f"https://{d}/{p[0]}/{r}", p[0], r
    return '', '', ''


def get_latest_github_package(url: str, ebuild: str,
                              settings: LivecheckSettings) -> tuple[str, str]:
    domain, owner, repo = extract_owner_repo(url)
    if not owner or not repo:
        return '', ''

    url = GITHUB_DOWNLOAD_URL % (domain)
    if not (r := get_content(url)):
        return '', ''

    results: list[dict[str, str]] = []
    for tag_id_element in etree.fromstring(r.text).findall('entry/id', RSS_NS):
        tag_id = tag_id_element.text

        tag = tag_id.split('/')[-1] if tag_id and '/' in tag_id else ''
        if tag := (tag_id.split('/')[-1] if tag_id and '/' in tag_id else ''):
            results.append({"tag": tag, "id": tag})

    if last_version := get_last_version(results, repo, ebuild, settings):
        url = GITHUB_DATE_URL % (owner, repo, last_version['id'])
        if not (r := get_content(url)):
            return last_version['version'], ''
        return last_version['version'], r.json()["object"]["sha"]
    return '', ''


def get_latest_github_commit(url: str, branch: str) -> tuple[str, str]:
    _, owner, repo = extract_owner_repo(url)
    if not owner or not repo:
        return '', ''

    return get_latest_github_commit2(owner, repo, branch)


def get_latest_github_commit2(owner: str, repo: str, branch: str) -> tuple[str, str]:
    url = GITHUB_COMMIT_URL % (owner, repo, branch)
    if not (r := get_content(url)):
        return '', ''
    d = r.json()["commit"]["commit"]["committer"]["date"][:10]
    try:
        dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
        formatted_date = dt.strftime("%Y%m%d")
    except ValueError:
        formatted_date = d[:10]
    return r.json()["commit"]["sha"], formatted_date


def is_github(url: str) -> bool:
    return bool(extract_owner_repo(url)[0])


def get_branch(url: str, ebuild: str, settings: LivecheckSettings) -> str:
    catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)

    # get branch from url
    parts = url.strip("/").split("/")
    if len(parts) >= 2 and parts[-2] == "commits":
        return parts[-1].replace(".atom", "")

    # get branch from settings
    if (branch := settings.branches.get(catpkg, '')):
        return branch

    # default branch is master
    if is_sha(urlparse(url).path):
        return 'master'

    return ''


def get_latest_github(url: str, ebuild: str, settings: LivecheckSettings) -> tuple[str, str, str]:
    last_version = top_hash = hash_date = ''

    if (branch := get_branch(url, ebuild, settings)):
        top_hash, hash_date = get_latest_github_commit(url, branch)
    else:
        last_version, top_hash = get_latest_github_package(url, ebuild, settings)

    return last_version, top_hash, hash_date
