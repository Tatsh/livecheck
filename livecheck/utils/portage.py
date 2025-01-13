from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
import logging
import os
import re
from typing import List
from itertools import chain

from portage.versions import catpkgsplit, vercmp
from ..settings import LivecheckSettings
import portage

__all__ = ('P', 'catpkg_catpkgsplit', 'get_first_src_uri', 'get_highest_matches',
           'get_highest_matches2', 'sort_by_v', 'get_repository_root_if_inside', 'compare_versions',
           'sanitize_version', 'get_distdir', 'fetch_ebuild', 'unpack_ebuild')

P = portage.db[portage.root]['porttree'].dbapi
logger = logging.getLogger(__name__)


def sort_by_v(a: str, b: str) -> int:
    cp_a, _, _, version_a = catpkg_catpkgsplit(a)
    cp_b, _, _, version_b = catpkg_catpkgsplit(b)
    if cp_a == cp_b:
        if version_a == version_b:
            return 0
        # Sort descending. First is taken with unique_justseen
        logger.debug(
            'Found multiple ebuilds of %s. Only the highest version ebuild will be considered.',
            cp_a,
        )
        return vercmp(version_b, version_a, silent=0) or 0
    return cp_a < cp_b


def mask_version(cp: str, version: str, restrict_version: str | None = 'full') -> str:
    if restrict_version == 'major':
        return cp + ':' + re.sub(r'\.\d+', '', version) + ':'
    if restrict_version == 'minor':
        return cp + ':' + re.sub(r'\.\d+\.\d+', '', version) + ':'
    return cp


def get_highest_matches(search_dir: str, repo_root: str, settings: LivecheckSettings) -> List[str]:
    result: dict[str, str] = {}
    for path in Path(search_dir).glob('**/*.ebuild'):
        dn = path.parent
        name = f'{dn.parent.name}/{dn.name}'
        if matches := P.xmatch('match-all', name):
            for m in matches:
                if P.findname2(m)[1] == repo_root:
                    cp_a, _, _, version_a = catpkg_catpkgsplit(m)
                    if '9999' in version_a or not cp_a or not version_a:
                        continue
                    restrict_version = settings.restrict_version.get(name, 'full')
                    cp_mask = mask_version(cp_a, version_a, restrict_version)
                    if cp_mask in result:
                        if vercmp(version_a, result[cp_mask]):
                            result[cp_mask] = version_a
                    else:
                        result[cp_mask] = version_a

    return [f"{cp}-{version}" for cp, version in result.items()]


def get_highest_matches2(names: Sequence[str], repo_root: str,
                         settings: LivecheckSettings) -> List[str]:
    result: dict[str, str] = {}
    for name in names:
        if matches := P.xmatch('match-all', name):
            for m in matches:
                if not repo_root or P.findname2(m)[1] == repo_root:
                    cp_a, _, _, version_a = catpkg_catpkgsplit(m)
                    if '9999' in version_a or not cp_a or not version_a:
                        continue
                    restrict_version = settings.restrict_version.get(name, 'full')
                    cp_mask = mask_version(cp_a, version_a, restrict_version)
                    if cp_mask in result:
                        if vercmp(version_a, result[cp_mask]):
                            result[cp_mask] = version_a
                    else:
                        result[cp_mask] = version_a

    return [f"{cp}-{version}" for cp, version in result.items()]


@lru_cache
def catpkg_catpkgsplit(atom: str) -> tuple[str, str, str, str]:
    """
    Split an atom string. This function always returns a four-string tuple.

    Parameters
    ----------
    atom : str
        String to split.

    Returns
    -------
    tuple[str, str, str, str]
        Tuple consisting of four strings.
    """
    result = catpkgsplit(atom)
    if not result or len(result) != 4:
        raise ValueError(f'Invalid atom: {atom}')

    cat, pkg, ebuild_version, revision = result

    if revision and revision != 'r0':
        full_version = f'{ebuild_version}-{revision}'
    else:
        full_version = ebuild_version

    return f'{cat}/{pkg}', cat, pkg, full_version


def get_first_src_uri(match: str, search_dir: str | None = None) -> str:
    try:
        if (found_uri := next((uri for uri in chain(
                *(x.split() for x in map(str, P.aux_get(match, ['SRC_URI'], mytree=search_dir))))
                               if uri.startswith(('http://', 'https://', 'mirror://', 'ftp://'))),
                              None)):
            return found_uri
    except KeyError:
        pass
    return ''


def get_repository_root_if_inside(directory: str) -> tuple[str, str]:
    # Get Portage configuration
    settings = portage.config(clone=portage.settings)

    # Get repositories from the settings object
    repos = settings['PORTDIR_OVERLAY'].split() + [settings['PORTDIR']]

    # Normalize the directory path to check
    directory = os.path.abspath(directory) + "/"
    selected_repo_root = ''
    selected_repo_name = ''

    # Check each repository
    for repo_root in repos:
        if os.path.isdir(repo_root):
            repo_root = os.path.abspath(repo_root)
            # Check if the directory is inside the repository root
            if directory.startswith(repo_root + "/"):
                # Select the most specific repository (deepest path)
                if selected_repo_root is None or len(repo_root) > len(selected_repo_root):
                    selected_repo_root = repo_root
                    selected_repo_name = os.path.basename(repo_root)

    if '/local/' in directory and not '/local/' in selected_repo_root:
        return '', ''

    # Return the most specific repository root, if found
    return selected_repo_root, selected_repo_name


def is_hash(str: str) -> bool:
    pattern = {
        'MD5': r'[0-9a-f]{32}',
        'SHA1': r'[0-9a-f]{40}',
        'SHA256': r'[0-9a-f]{64}',
        'SHA512': r'[0-9a-f]{128}',
    }
    for _, value in pattern.items():
        if re.match(value, str):
            return True
    return False


def is_version_development(version: str) -> bool:
    if re.search(r'(alpha|beta|pre|dev|rc)', version, re.IGNORECASE):
        return True
    return False


# Sanitize version to Gentoo Ebuild format
# info: https://dev.gentoo.org/~gokturk/devmanual/pr65/ebuild-writing/file-format/index.html
def sanitize_version(version: str) -> str:
    if not version:
        return '0'

    # Force convert version to string to fix version like 1.8
    version = str(version)

    if is_hash(version):
        return version

    # remove initial "2-" found in dev-libs/libpcre2, net-analyzer/barnyard2, etc..
    if version.startswith('2-'):
        version = version[2:]

    version = re.sub(r'(\d)_(\d)', r'\1.\2', version)
    pattern = r"(\d+(\.\d+)*[a-z]?(_(alpha|beta|pre|rc|p)\d*)*(-r\d+)?)"

    match = re.search(pattern, version, re.IGNORECASE)

    if match:
        if match.group(1) != version:
            logger.debug(f'Version {version} sanitized to {match.group(1)}')
        return match.group(1)
    else:
        return version


def compare_versions(old: str, new: str, development: bool = False, old_sha: str = "") -> bool:
    if is_hash(new):
        return old_sha != new

    # check if is a beta, alpa, pre or rc version and not accept this version
    if not development and is_version_development(new):
        logger.debug(f'Not permitted development version {new}')
        return False

    return bool(vercmp(sanitize_version(old), sanitize_version(new), silent=0) == -1)


def get_distdir() -> str:
    settings = portage.config(clone=portage.settings)
    distdir = settings.get('DISTDIR')
    if distdir:
        return str(distdir)

    return '/var/cache/distfiles'


def fetch_ebuild(ebuild_path: str) -> bool:
    settings = portage.config(clone=portage.settings)

    return bool(portage.doebuild(ebuild_path, 'fetch', settings=settings, mytree='porttree') == 0)


def digest_ebuild(ebuild_path: str) -> bool:
    settings = portage.config(clone=portage.settings)

    return bool(portage.doebuild(ebuild_path, 'digest', settings=settings, tree='porttree') == 0)


def unpack_ebuild(ebuild_path: str) -> str:
    settings = portage.config(clone=portage.settings)

    if portage.doebuild(ebuild_path, 'clean', settings=settings, tree='porttree') != 0:
        return ''

    if portage.doebuild(ebuild_path, 'unpack', settings=settings, tree='porttree') != 0:
        return ''

    workdir = settings["WORKDIR"]

    if os.path.exists(workdir) and os.path.isdir(workdir):
        return str(workdir)

    return ''
