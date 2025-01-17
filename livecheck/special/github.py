from urllib.parse import urlparse
import re
import xml.etree.ElementTree as etree
from datetime import datetime
from loguru import logger
import requests

from ..utils.portage import is_version_development
from ..utils import (session_init)

from ..constants import (RSS_NS)

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


def get_latest_github_package(url: str,
                              development: bool = False,
                              restrict_version: str = '') -> tuple[str, str, str]:

    domain, owner, repo = extract_owner_repo(url)
    if not owner or not repo:
        return '', '', ''

    session = session_init('atom')

    r = session.get(f"{domain}/tags.atom")
    if r.status_code != 200:
        return '', '', ''
    r.raise_for_status()

    results = []

    for t in etree.fromstring(r.text).findall('entry/title', RSS_NS):
        cleaned_name = re.sub(r"^[^\d]+", "", t.text or "")
        match = re.match(r"^(\d+(?:\.\d+){0,2})", cleaned_name)
        if match:
            cleaned_name = match.group(1)
        # skip if the tag is not a version
        if not re.match(r"^\d+(\.\d+){0,2}$", cleaned_name):
            continue
        results.append({"version": cleaned_name, "tag": t})

    for result in results:
        version = result["version"]
        if not version.startswith(restrict_version):
            continue
        if not is_version_development(version) or development:
            try:
                session = session_init('github')
                r = session.get(
                    f"https://api.github.com/repos/{owner}/{repo}/git/refs/tags/{result['tag'].text}"
                )
                if r.status_code != 200:
                    return '', '', ''
                return version, r.json()["object"]["sha"], ''
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {e}")
                return '', '', ''

    return '', '', ''


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
