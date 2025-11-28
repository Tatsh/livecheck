"""Checksum functions."""
from __future__ import annotations

from pathlib import Path
import re

from livecheck.utils import get_content, get_last_modified, hash_url
from livecheck.utils.portage import catpkg_catpkgsplit

from .utils import EbuildTempFile

__all__ = ('get_latest_checksum_package', 'get_latest_location_checksum_package')

PATTERN = re.compile(r'^DIST\s+(?P<file>\S+)\s+(?P<size>\d+)\s+BLAKE2B\s+'
                     r'(?P<blake2b>[a-fA-F0-9]+)\s+SHA512\s+(?P<sha512>[a-fA-F0-9]+)$')


def get_latest_checksum_package(
    url: str,
    ebuild: str,
    repo_root: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> tuple[str, str, str]:
    """Get the latest version of a package based on its checksum."""
    catpkg, _, _, version = catpkg_catpkgsplit(ebuild)
    manifest_file = Path(repo_root) / catpkg / 'Manifest'
    bn = Path(url).name

    # Gather all DIST line matches first
    dist_lines: list[re.Match[str]] = []
    with Path(manifest_file).open(encoding='utf-8') as f:
        dist_lines.extend(m for line in f if (m := PATTERN.match(line)))

    # If only one DIST entry, check it regardless of filename
    if len(dist_lines) == 1:
        m = dist_lines[0]
        blake2, sha512, _ = hash_url(url, headers=headers, params=params)
        if blake2 != m.group('blake2b') or sha512 != m.group('sha512'):
            last_modified = get_last_modified(url, headers=headers, params=params)
            return version, last_modified, url
    else:
        # Multiple entries: match by filename
        for m in dist_lines:
            if m.group('file') == bn:
                blake2, sha512, _ = hash_url(url, headers=headers, params=params)
                if blake2 != m.group('blake2b') or sha512 != m.group('sha512'):
                    last_modified = get_last_modified(url, headers=headers, params=params)
                    return version, last_modified, url

    return '', '', ''


def get_latest_location_checksum_package(
    url: str,
    ebuild: str,
    repo_root: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> tuple[str, str, str]:
    """Get the latest version of a package based on Location header and checksum."""
    # First, follow the redirect to get the Location header
    r = get_content(url, allow_redirects=False, headers=headers, params=params)

    # Get the Location header from the redirect
    location_url = r.headers.get('Location', '')
    if not location_url:
        return '', '', ''

    # Now check the checksum of the final URL
    return get_latest_checksum_package(location_url,
                                       ebuild,
                                       repo_root,
                                       headers=headers,
                                       params=params)


def update_checksum_metadata(ebuild: str,
                             url: str,
                             repo_root: str,
                             headers: dict[str, str] | None = None,
                             params: dict[str, str] | None = None) -> None:
    """Update the checksum metadata in the Manifest file."""
    catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)
    manifest_file = Path(repo_root) / catpkg / 'Manifest'
    blake2, sha512, size = hash_url(url, headers=headers, params=params)
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
