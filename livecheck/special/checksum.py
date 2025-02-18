from pathlib import Path
import re

from ..utils import get_last_modified, hash_url
from ..utils.portage import catpkg_catpkgsplit

__all__ = ("get_latest_checksum_package",)


def get_latest_checksum_package(url: str, ebuild: str, repo_root: str) -> tuple[str, str]:
    catpkg, _, _, version = catpkg_catpkgsplit(ebuild)

    pattern = re.compile(r'^DIST\s+(?P<file>\S+)\s+(?P<size>\d+)\s+BLAKE2B\s+'
                         r'(?P<blake2b>[a-fA-F0-9]+)\s+SHA512\s+(?P<sha512>[a-fA-F0-9]+)$')
    manifest_file = Path(repo_root) / catpkg / 'Manifest'
    bn = Path(url).name
    with open(manifest_file, encoding='utf-8') as f:
        for line in f.readlines():
            m = pattern.match(line)
            if m and m.group('file') == bn:
                blake2, sha512 = hash_url(url)
                if blake2 != m.group('blake2b') or sha512 != m.group('sha512'):
                    last_modified = get_last_modified(url)
                    return version, last_modified

    return '', ''
