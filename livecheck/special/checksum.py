"""Checksum functions."""
from __future__ import annotations

from pathlib import Path
import re

from livecheck.utils import get_last_modified, hash_url
from livecheck.utils.portage import catpkg_catpkgsplit

from .utils import EbuildTempFile

__all__ = ('get_latest_checksum_package',)

PATTERN = re.compile(r'^DIST\s+(?P<file>\S+)\s+(?P<size>\d+)\s+BLAKE2B\s+'
                     r'(?P<blake2b>[a-fA-F0-9]+)\s+SHA512\s+(?P<sha512>[a-fA-F0-9]+)$')


def get_latest_checksum_package(url: str, ebuild: str, repo_root: str) -> tuple[str, str, str]:
    """Get the latest version of a package based on its checksum."""
    catpkg, _, _, version = catpkg_catpkgsplit(ebuild)
    manifest_file = Path(repo_root) / catpkg / 'Manifest'
    bn = Path(url).name

    with Path(manifest_file).open(encoding='utf-8') as f:
        for line in f:
            m = PATTERN.match(line)
            if m and m.group('file') == bn:
                blake2, sha512, _ = hash_url(url)
                if blake2 != m.group('blake2b') or sha512 != m.group('sha512'):
                    last_modified = get_last_modified(url)
                    return version, last_modified, url

    return '', '', ''


def update_checksum_metadata(ebuild: str, url: str, repo_root: str) -> None:
    """Update the checksum metadata in the Manifest file."""
    catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)
    manifest_file = Path(repo_root) / catpkg / 'Manifest'
    blake2, sha512, size = hash_url(url)
    bn = Path(url).name

    with (
            EbuildTempFile(str(manifest_file)) as temp_file,
            temp_file.open('w', encoding='utf-8') as tf,
            Path(manifest_file).open('r', encoding='utf-8') as f,
    ):
        for line in f:
            m = PATTERN.match(line)
            if m and m.group('file') == bn:
                tf.write(f'DIST {bn} {size} BLAKE2B {blake2} SHA512 {sha512}\n')
            else:
                tf.write(line)
