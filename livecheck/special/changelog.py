"""Special changelog handling."""
from __future__ import annotations

from typing import TYPE_CHECKING
import re

from livecheck.utils import get_content
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

if TYPE_CHECKING:
    from livecheck.settings_model import LivecheckSettings

__all__ = ('get_latest_changelog_package',)

CHANGELOG_HEADING_RE = re.compile(
    r'^\s{0,3}#{1,6}\s+(?:\[(?P<bracketed>[vV]?\d[\w.+-]*)\]|'
    r'(?P<plain>[vV]?\d[\w.+-]*))(?=\s|$)', re.MULTILINE)


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
    catpkg = catpkg_catpkgsplit(ebuild)[0]
    if not (r := await get_content(url,
                                   headers=settings.request_headers.get(catpkg, {}),
                                   params=settings.request_params.get(catpkg, {}),
                                   method=settings.request_method.get(catpkg, 'GET'),
                                   data=settings.request_data.get(catpkg, {}))):
        return ''

    results = [{
        'tag': match.group('bracketed') or match.group('plain')
    } for match in CHANGELOG_HEADING_RE.finditer(r.text or '')]
    if last_version := get_last_version(results, '', ebuild, settings):
        return last_version['version']

    return ''
