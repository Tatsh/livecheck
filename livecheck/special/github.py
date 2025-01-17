import requests
import re
from urllib.parse import urlparse
from datetime import datetime
from loguru import logger
import contextlib

from ..utils.portage import is_version_development
from ..utils import (get_github_api_credentials)

__all__ = ("get_latest_github_package", "get_latest_github_commit")


def extract_owner_repo(url: str) -> tuple[str, str]:
    u = urlparse(url)
    n = u.netloc
    m = re.match(r'^([^\.]+)\.github\.(io|com)$', n)
    if m:
        p = [x for x in u.path.split('/') if x]
        if not p: return '', ''
        return m.group(1), p[0]
    if 'github.' in n:
        p = [x for x in u.path.split('/') if x]
        if len(p) < 2: return '', ''
        return p[0], p[1].replace('.git', '')
    return '', ''


def get_latest_github_package(url: str,
                              development: bool = False,
                              restrict_version: str = '') -> tuple[str, str, str]:

    owner, repo = extract_owner_repo(url)
    if not owner or not repo:
        return '', '', ''

    headers = {}
    session = requests.Session()
    token = get_github_api_credentials()
    if not token:
        logger.warning("No GitHub API token found")
    with contextlib.suppress(KeyError):
        headers['Authorization'] = f'token {get_github_api_credentials()}'

    r = session.get(f"https://api.github.com/repos/{owner}/{repo}/tags",
                    headers=headers,
                    timeout=30)
    if r.status_code != 200:
        return '', '', ''

    results = []
    for t in r.json():
        results.append({"tag": t["name"], "id": t["commit"]["sha"], "commit": t["commit"]["url"]})

    for result in results:
        version = result["tag"]
        if not version.startswith(restrict_version):
            continue
        if not is_version_development(version) or development:
            try:
                cr = session.get(result["commit"], headers=headers, timeout=30)
                if cr.status_code != 200:
                    continue
                d = cr.json()["commit"]["committer"]["date"][:10]
                try:
                    dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
                    formatted_date = dt.strftime("%Y-%m-%d")
                except:
                    formatted_date = d[:10]
                return version, result["id"], formatted_date
            except requests.exceptions.HTTPError as e:
                logger.error(f"URL error: {e}")
                return '', '', ''

    return '', '', ''


def get_latest_github_commit(url: str, branch: str = 'master') -> tuple[str, str]:
    owner, repo = extract_owner_repo(url)
    if not owner or not repo:
        return '', ''

    headers = {}
    session = requests.Session()
    token = get_github_api_credentials()
    if not token:
        logger.warning("No GitHub API token found")
    with contextlib.suppress(KeyError):
        headers['Authorization'] = f'token {get_github_api_credentials()}'

    r = session.get(f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}",
                    headers=headers,
                    timeout=30)
    if r.status_code != 200:
        return '', ''
    j = r.json()
    d = j["commit"]["commit"]["committer"]["date"][:10]
    try:
        dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
        formatted_date = dt.strftime("%Y-%m-%d")
    except:
        formatted_date = d[:10]
    return j["commit"]["sha"], formatted_date
