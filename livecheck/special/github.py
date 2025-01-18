from urllib.parse import urlparse
from typing import List, Dict
import re
import xml.etree.ElementTree as etree
from datetime import datetime
from loguru import logger
from portage.versions import vercmp

from ..settings import LivecheckSettings
from ..utils.portage import is_version_development
from ..utils import (session_init)

from ..constants import (RSS_NS)

from ..utils.portage import sanitize_version, catpkg_catpkgsplit

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

    results = []

    for entry in etree.fromstring(r.text).findall('entry', RSS_NS):
        tag_id_element = entry.find('id', RSS_NS)
        tag_id = tag_id_element.text if tag_id_element is not None else 'Desconocido'
        tag = tag_id.split('/')[-1] if tag_id and '/' in tag_id else tag_id
        tag_title_element = entry.find('title', RSS_NS)
        tag_title = tag_title_element.text if tag_title_element is not None else 'Desconocido'
        results.append({"tag": tag, "id": tag})
    """
    for t in etree.fromstring(r.text).findall('entry/title', RSS_NS):
        results.append({"tag": t.text, "tag": t})
    for t in etree.fromstring(r.text).findall('entry/title', RSS_NS):
        title = t["title"]
        tag = t.id.split('/')[-1] if '/' in tag_id else tag_id
        results.append({"tag": t.text, "id": t})
    """

    result = get_last_version(results, repo, ebuild, development, restrict_version, settings)
    if result:
        session = session_init('github')
        r = session.get(f"https://api.github.com/repos/{owner}/{repo}/git/refs/tags/{result['id']}")
        if r.status_code != 200:
            return result['version'], ''
        return result['version'], r.json()["object"]["sha"]
    return '', ''


def get_last_version(results: List[Dict[str, str]], repo: str, ebuild: str, development: bool,
                     restrict_version: str, settings: LivecheckSettings) -> Dict[str, str]:
    logger.debug(f'Result count: {len(results)}')

    catpkg, _, _, ebuild_version = catpkg_catpkgsplit(ebuild)
    last_version = {}

    for result in results:
        tag = version = result["tag"]
        if catpkg in settings.regex_version:
            logger.debug(f'Applying regex {tag} -> {version}')
            regex, replace = settings.regex_version[catpkg]
            version = re.sub(regex, replace, version)
        else:
            version = sanitize_version(version, repo)
            logger.debug(f"Convert Tag: {tag} -> {version}")
        # Check valid version
        try:
            _, _, _, _ = catpkg_catpkgsplit(ebuild)
        except ValueError:
            logger.debug(f"Skip non-version tag: {version}")
            continue
        if not version.startswith(restrict_version):
            continue
        if is_version_development(ebuild_version) or (not is_version_development(version)
                                                      or development):
            last = last_version.get('version', '')
            if not last or bool(vercmp(last, version) == -1):
                last_version = result.copy()
                last_version['version'] = version

    return last_version


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
