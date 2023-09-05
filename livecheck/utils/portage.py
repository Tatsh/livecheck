from functools import cmp_to_key
from os.path import basename, dirname
from typing import Iterator, Sequence
import glob

from loguru import logger
from portage.versions import catpkgsplit, vercmp
import portage

__all__ = ('P', 'catpkg_catpkgsplit', 'find_highest_match_ebuild_path', 'get_first_src_uri',
           'get_highest_matches', 'get_highest_matches2')

P = portage.db[portage.root]['porttree'].dbapi  # pylint: disable=no-member


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


def find_highest_match_ebuild_path(cp: str, search_dir: str) -> str:
    def cmp(a: tuple[str, str], b: tuple[str, str]) -> int:
        split_a = catpkgsplit(a[1])
        split_b = catpkgsplit(b[1])
        assert len(split_a) == 4
        assert len(split_b) == 4
        return vercmp(split_a[3], split_b[3]) or 0  # type: ignore[misc]

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
