import requests
import re
from urllib.parse import urlparse
from datetime import datetime
from loguru import logger

from ..utils.portage import is_version_development
from ..utils import (session_init)

__all__ = ("get_latest_github_package", "get_latest_github_commit")


def extract_owner_repo(url: str) -> tuple[str, str]:
    u = urlparse(url)
    n = u.netloc
    m = re.match(r'^([^\.]+)\.github\.(io|com)$', n)
    if m:
        p = [x for x in u.path.split('/') if x]
        if not p:
            return '', ''
        return m.group(1), p[0]
    if 'github.' in n:
        p = [x for x in u.path.split('/') if x]
        if len(p) < 2:
            return '', ''
        return p[0], p[1].replace('.git', '')
    return '', ''


def get_latest_github_package(url: str,
                              development: bool = False,
                              restrict_version: str = '') -> tuple[str, str, str]:

    owner, repo = extract_owner_repo(url)
    if not owner or not repo:
        return '', '', ''

    session = session_init('github')

    r = session.get(f"https://api.github.com/repos/{owner}/{repo}/tags")
    if r.status_code != 200:
        return '', '', ''

    results: list[dict[str, str]] = []

    for t in r.json():
        original_name = t["name"]
        cleaned_name = re.sub(r"^[^\d]+", "", original_name)
        match = re.match(r"^(\d+(?:\.\d+){0,2})", cleaned_name)
        if match:
            cleaned_name = match.group(1)
        # skip if the tag is not a version
        if not re.match(r"^\d+(\.\d+){0,2}$", cleaned_name):
            continue
        results.append({
            "tag": cleaned_name,
            "id": t["commit"]["sha"],
            "commit": t["commit"]["url"]
        })

    # sort results by version in numerical x.y.z order in descending order
    results.sort(key=lambda x: tuple(map(int, x["tag"].split('.'))), reverse=True)

    for result in results:
        version = result["tag"]
        if not version.startswith(restrict_version):
            continue
        if not is_version_development(version) or development:
            try:
                cr = session.get(result["commit"])
                if cr.status_code != 200:
                    continue
                d = cr.json()["commit"]["committer"]["date"][:10]
                try:
                    dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
                    formatted_date = dt.strftime("%Y-%m-%d")
                except ValueError:
                    formatted_date = d[:10]
                return version, result["id"], formatted_date
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {e}")
                return '', '', ''

    return '', '', ''


def get_latest_github_commit(url: str, branch: str = 'master') -> tuple[str, str]:
    owner, repo = extract_owner_repo(url)
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
        formatted_date = dt.strftime("%Y-%m-%d")
    except ValueError:
        formatted_date = d[:10]
    return j["commit"]["sha"], formatted_date
