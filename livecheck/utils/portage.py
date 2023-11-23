from functools import cmp_to_key
from os.path import basename, dirname
from typing import Iterator, Sequence
import glob

from loguru import logger
from portage.versions import catpkgsplit, vercmp
import portage

__all__ = ('P', 'catpkg_catpkgsplit', 'find_highest_match_ebuild_path', 'get_first_src_uri',
           'get_highest_matches', 'get_highest_matches2', 'sort_by_v')

P = portage.db[portage.root]['porttree'].dbapi  # pylint: disable=no-member


def sort_by_v(a: str, b: str) -> int:
    cp_a, _cat_a, _pkg_b, version_a = catpkg_catpkgsplit(a)
    cp_b, _cat_b, _pkg_b, version_b = catpkg_catpkgsplit(b)
    if cp_a == cp_b:
        if version_a == version_b:
            return 0
        # Sort descending. First is taken with unique_justseen
        logger.debug(f'Found multiple ebuilds of {cp_a}. Only the highest version ebuild will be '
                     'considered.')
        return vercmp(version_b, version_a, silent=0) or 0
    return cp_a < cp_b


def get_highest_matches(search_dir: str) -> Iterator[str]:
    for path in glob.glob(f'{search_dir}/**/*.ebuild', recursive=True):
        dn = dirname(path)
        name = f'{basename(dirname(dn))}/{basename(dn)}'
        if matches := P.xmatch('match-visible', name):
            for m in matches:
                if P.findname2(m)[1] == search_dir:
                    yield m


def get_highest_matches2(names: Sequence[str], search_dir: str) -> Iterator[str]:
    for name in names:
        if matches := P.xmatch('match-visible', name):
            for m in matches:
                candidate = P.findname2(m)[1]
                logger.debug(f'Checking: {candidate} == {search_dir} ?')
                if candidate == search_dir:
                    yield m


def get_3rd_of_4(tup: tuple[str, str] | tuple[str, str, str] | tuple[str, str, str, str]) -> str:
    match tup:
        case (_x, _y, z, _w):
            return z
        case _:
            raise TypeError


def find_highest_match_ebuild_path(cp: str, search_dir: str) -> str:
    def cmp(a: tuple[str, str], b: tuple[str, str]) -> int:
        return vercmp(get_3rd_of_4(catpkgsplit(a[1])), get_3rd_of_4(catpkgsplit(b[1]))) or 0

    items: list[tuple[str, str]] = []
    for atom in P.match(cp):
        ebuild_path, tree = P.findname2(atom)
        if ebuild_path and tree == search_dir:
            items.append((ebuild_path, atom))
    return sorted(items, key=cmp_to_key(cmp))[-1][0]


def catpkg_catpkgsplit(s: str) -> tuple[str, str, str, str]:
    result = catpkgsplit(s)
    match result:
        case [cat, pkg, ebuild_version]:
            return f'{cat}/{pkg}', cat, pkg, ebuild_version
        case [cat, pkg, ebuild_version, _]:
            return f'{cat}/{pkg}', cat, pkg, ebuild_version
        case _:
            print(result)
            raise ValueError()


def get_first_src_uri(match: str, search_dir: str | None = None) -> str:
    return P.aux_get(match, ['SRC_URI'], mytree=search_dir)[0].split(' ')[0]
