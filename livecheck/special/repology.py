"""Repology functions."""
from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.utils import get_content
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

if TYPE_CHECKING:
    from livecheck.settings import LivecheckSettings

__all__ = ('get_latest_repology',)

REPOLOGY_DOWNLOAD_URL = 'https://repology.org/api/v1/project/%s'


def get_latest_repology(ebuild: str, settings: LivecheckSettings, package: str = '') -> str:
    """Get the latest version of a package from Repology."""
    catpkg, _, pkg, _ = catpkg_catpkgsplit(ebuild)

    results: list[dict[str, str]] = []

    if package:
        pkg = package
    url = REPOLOGY_DOWNLOAD_URL % (pkg)
    if not (r := get_content(url)):
        url = REPOLOGY_DOWNLOAD_URL % (pkg.split('-')[0])
        if not (r := get_content(url)):
            return ''

    for release in r.json():
        if release.get('srcname') == pkg and (release.get('status') != 'devel'
                                              or settings.is_devel(catpkg)):
            results.extend([{'tag': release.get('version')}])

    if last_version := get_last_version(results, '', ebuild, settings):
        return last_version['version']

    return ''
