from collections.abc import Iterator, Sequence
from functools import cmp_to_key, lru_cache
from pathlib import Path
import logging
import os

from portage.versions import catpkgsplit, vercmp
import portage

__all__ = (
    'P',
    'catpkg_catpkgsplit',
    'find_highest_match_ebuild_path',
    'get_first_src_uri',
    'get_highest_matches',
    'get_highest_matches2',
    'sort_by_v',
    'get_repository_root_if_inside',
)

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


def get_highest_matches(search_dir: str, repo_root: str) -> Iterator[str]:
    for path in Path(search_dir).glob('**/*.ebuild'):
        dn = path.parent
        name = f'{dn.parent.name}/{dn.name}'
        if matches := P.xmatch('match-all', name):
            for m in matches:
                if P.findname2(m)[1] == repo_root:
                    yield m


def get_highest_matches2(names: Sequence[str], search_dir: str) -> Iterator[str]:
    for name in names:
        if matches := P.xmatch('match-all', name):
            for m in matches:
                candidate = P.findname2(m)[1]
                logger.debug('Checking: %s == %s ?', candidate, search_dir)
                if candidate == search_dir:
                    yield m


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
    match result:
        case [cat, pkg, ebuild_version]:
            return f'{cat}/{pkg}', cat, pkg, ebuild_version
        case [cat, pkg, ebuild_version, _]:
            return f'{cat}/{pkg}', cat, pkg, ebuild_version
        case _:
            raise ValueError(result)


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
