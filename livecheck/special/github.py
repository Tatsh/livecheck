from urllib.parse import urlparse
import re
import xml.etree.ElementTree as etree
from datetime import datetime

from ..settings import LivecheckSettings
from ..utils.portage import get_last_version
from ..utils import session_init

from ..constants import RSS_NS

__all__ = ("get_latest_github_package", "get_latest_github_commit")


def extract_owner_repo(url: str) -> tuple[str, str, str]:
    u = urlparse(url)
    d = u.netloc
    n = u.netloc
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


def get_latest_github_package(url: str, ebuild: str, development: bool, restrict_version: str,
                              settings: LivecheckSettings) -> tuple[str, str]:

    domain, owner, repo = extract_owner_repo(url)
    if not owner or not repo:
        return '', ''

    session = session_init('atom')

    r = session.get(f"{domain}/tags.atom")
    if r.status_code != 200:
        return '', ''
    r.raise_for_status()

    results: list[dict[str, str]] = []
    for tag_id_element in etree.fromstring(r.text).findall('entry/id', RSS_NS):
        tag_id = tag_id_element.text
        tag = tag_id.split('/')[-1] if tag_id and '/' in tag_id else ''
        if tag:
            results.append({"tag": tag, "id": tag})

    last_version = get_last_version(results, repo, ebuild, development, restrict_version, settings)
    if last_version:
        session = session_init('github')
        r = session.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/refs/tags/{last_version['id']}")
        if r.status_code != 200:
            return last_version['version'], ''
        return last_version['version'], r.json()["object"]["sha"]
    return '', ''


def get_latest_github_commit(url: str, branch: str = 'master') -> tuple[str, str]:
    _, owner, repo = extract_owner_repo(url)
    if not owner or not repo:
        return '', ''

    session = session_init('github')

    r = session.get(f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}")
    if r.status_code != 200:
        return '', ''
    j = r.json()
    d = j["commit"]["commit"]["committer"]["date"][:10]
    try:
        dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
        formatted_date = dt.strftime("%Y%m%d")
    except ValueError:
        formatted_date = d[:10]
    return j["commit"]["sha"], formatted_date
