from collections.abc import Sequence
from functools import cmp_to_key, lru_cache
from pathlib import Path
import logging
import os
import re
from typing import List

from portage.versions import catpkgsplit, vercmp, pkgcmp
import portage

__all__ = ('P', 'catpkg_catpkgsplit', 'find_highest_match_ebuild_path', 'get_first_src_uri',
           'get_highest_matches', 'get_highest_matches2', 'sort_by_v',
           'get_repository_root_if_inside', 'compare_versions', 'sanitize_version')

P = portage.db[portage.root]['porttree'].dbapi
logger = logging.getLogger(__name__)


def sort_by_v(a: str, b: str) -> int:
    cp_a, _cat_a, _pkg_b, version_a = catpkg_catpkgsplit(a)
    cp_b, _cat_b, _pkg_b, version_b = catpkg_catpkgsplit(b)
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


def get_highest_matches(search_dir: str, repo_root: str) -> List[str]:
    result = {}
    for path in Path(search_dir).glob('**/*.ebuild'):
        dn = path.parent
        name = f'{dn.parent.name}/{dn.name}'
        if matches := P.xmatch('match-all', name):
            for m in matches:
                if P.findname2(m)[1] == repo_root:
                    cp_a, _, _, version_a = catpkg_catpkgsplit(m)
                    if '9999' in version_a or not cp_a or not version_a:
                        continue
                    if cp_a in result:
                        if vercmp(version_a, result[cp_a]):
                            result[cp_a] = version_a
                    else:
                        result[cp_a] = version_a

    return [f"{cp}-{version}" for cp, version in result.items()]


def get_highest_matches2(names: Sequence[str], repo_root: str) -> List[str]:
    result = {}
    for name in names:
        if matches := P.xmatch('match-all', name):
            for m in matches:
                if P.findname2(m)[1] == repo_root:
                    cp_a, _, _, version_a = catpkg_catpkgsplit(m)
                    if '9999' in version_a or not cp_a or not version_a:
                        continue
                    if cp_a in result:
                        if vercmp(version_a, result[cp_a]):
                            result[cp_a] = version_a
                    else:
                        result[cp_a] = version_a

    return [f"{cp}-{version}" for cp, version in result.items()]


def get_3rd_of_4(tup: tuple[str, str] | tuple[str, str, str] | tuple[str, str, str, str]) -> str:
    match tup:
        case (_x, _y, z, _w):
            return z
        case _:
            raise TypeError


def find_highest_match_ebuild_path(input_atom: str, search_dir: str) -> str:
    """
    Given a catpkg string and search directory, finds the highest version matching ebuild file path.

    Parameters
    ----------
    input_atom : str
        Atom string.

    search_dir : str
        Path to search.

    Returns
    -------
    str
        The ebuild file path. This will raise ``IndexError`` otherwise.
    """
    def cmp(a: tuple[str, str], b: tuple[str, str]) -> int:
        return vercmp(get_3rd_of_4(catpkgsplit(a[1])), get_3rd_of_4(catpkgsplit(b[1]))) or 0

    items: list[tuple[str, str]] = []
    for atom in P.match(input_atom):
        ebuild_path, tree = P.findname2(atom)
        if ebuild_path and tree == search_dir:
            items.append((ebuild_path, atom))
    return sorted(items, key=cmp_to_key(cmp))[-1][0]


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
    if not result:
        raise ValueError(f'Invalid atom: {atom}')

    cat, pkg, ebuild_version, revision = result

    if revision and revision != 'r0':
        full_version = f'{ebuild_version}-{revision}'
    else:
        full_version = ebuild_version

    return f'{cat}/{pkg}', cat, pkg, full_version


def get_first_src_uri(match: str, search_dir: str | None = None) -> str:
    for uri in P.aux_get(match, ['SRC_URI'], mytree=search_dir):
        for line in uri.split():
            if line.startswith(('http://', 'https://')):
                return line
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


def compare_versions(old: str, new: str) -> bool:
    if is_hash(old) and is_hash(new):
        return old != new

    # check if is a beta, alpa, pre or rc version and not accept this version
    if is_version_development(new):
        logger.debug(f'Not permitted development version {new}')
        return False

    return vercmp(sanitize_version(new), sanitize_version(old), silent=0) == -1
