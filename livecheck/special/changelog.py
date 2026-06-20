"""Special changelog handling."""
from __future__ import annotations

from typing import TYPE_CHECKING
import re

from livecheck.utils import get_content
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

if TYPE_CHECKING:
    from livecheck.settings_model import LivecheckSettings

__all__ = ('get_latest_changelog_package',)

_CHANGELOG_HEADING_RE = re.compile(
    r'^\s{0,3}#{1,6}\s+(?:\[(?P<bracketed>[vV]?\d[\w.+-]*)\]|'
    r'(?P<plain>[vV]?\d[\w.+-]*))(?=\s|$)', re.MULTILINE)
# Matches a date-only heading such as ``2024-01-31`` so it is not mistaken for a version.
_ISO_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
# Matches a date-like ebuild version such as ``20240131``, ``2024.01.31``, or ``2024-01-31``.
_DATE_VERSION_RE = re.compile(r'^\d{4}[.-]?\d{2}[.-]?\d{2}')


async def get_latest_changelog_package(ebuild: str, url: str, settings: LivecheckSettings) -> str:
    """
    Get the latest version of a package from a Markdown changelog.

    Parameters
    ----------
    ebuild : str
        Ebuild atom string.
    url : str
        URL of the changelog document to scan.
    settings : LivecheckSettings
        Livecheck settings for HTTP behaviour and version filtering.

    Returns
    -------
    str
        Latest version found in changelog headings, or an empty string if none.
    """
    catpkg, _, _, ebuild_version = catpkg_catpkgsplit(ebuild)
    if not (r := await get_content(url,
                                   headers=settings.request_headers.get(catpkg, {}),
                                   params=settings.request_params.get(catpkg, {}),
                                   method=settings.request_method.get(catpkg, 'GET'),
                                   data=settings.request_data.get(catpkg, {}))):
        return ''

    # Date-only headings (such as ``2024-01-31``) are normalised by ``sanitize_version`` into
    # Portage-valid versions and would otherwise win over real semantic-versioning tags. Keep them
    # only when the ebuild itself uses a date-like version.
    ebuild_is_date = bool(_DATE_VERSION_RE.match(ebuild_version))
    results = [{
        'tag': tag
    } for match in _CHANGELOG_HEADING_RE.finditer(r.text or '')
               if (tag := match.group('bracketed') or match.group('plain')) and (
                   ebuild_is_date or not _ISO_DATE_RE.match(tag))]
    if last_version := get_last_version(results, '', ebuild, settings):
        return last_version['version']

    return ''
