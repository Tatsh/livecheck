"""NuGet functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse
import re

from livecheck.utils import get_content
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

if TYPE_CHECKING:
    from livecheck.settings_model import LivecheckSettings

__all__ = ('NUGET_METADATA', 'extract_project', 'get_latest_nuget_metadata',
           'get_latest_nuget_package', 'is_nuget')

NUGET_DOWNLOAD_URL = 'https://api.nuget.org/v3-flatcontainer/%s/index.json'
NUGET_METADATA = 'nuget'
"""Metadata key identifying NuGet remote-id entries.

:meta hide-value:
"""

_NUGET_HOSTS = frozenset({'api.nuget.org', 'nuget.org', 'www.nuget.org'})
_NUPKG_RE = re.compile(r'^(?P<id>[^/]+?)\.(?P<ver>\d.*?)\.nupkg$', re.IGNORECASE)


def extract_project(url: str) -> str:
    """
    Extract a NuGet package ID from a URL.

    Parameters
    ----------
    url : str
        URL pointing at a NuGet artefact, package page, or flat-container endpoint.

    Returns
    -------
    str
        Package ID in lower case, or an empty string if not recognised as NuGet.
    """
    parsed = urlparse(url)
    if parsed.netloc not in _NUGET_HOSTS:
        return ''
    parts = [p for p in parsed.path.split('/') if p]
    if not parts:
        return ''
    # https://www.nuget.org/packages/<id>[/<ver>]
    if parts[0] == 'packages' and len(parts) >= 2:  # ruff:ignore[magic-value-comparison]
        return parts[1].lower()
    # https://www.nuget.org/api/v2/package/<id>/<ver>
    if (len(parts) >= 4 and parts[0] == 'api'
            and parts[2] == 'package'):  # ruff:ignore[magic-value-comparison]
        return parts[3].lower()
    # https://api.nuget.org/v3-flatcontainer/<id>/...
    if parts[0] == 'v3-flatcontainer' and len(parts) >= 2:  # ruff:ignore[magic-value-comparison]
        if (len(parts) >= 3  # ruff:ignore[magic-value-comparison]
                and (m := _NUPKG_RE.match(parts[-1]))):
            return m.group('id').lower()
        return parts[1].lower()
    return ''


def is_nuget(url: str) -> bool:
    """
    Check whether the URL is a NuGet URL.

    Parameters
    ----------
    url : str
        URL to inspect.

    Returns
    -------
    bool
        ``True`` if the URL references a known NuGet endpoint, otherwise ``False``.
    """
    return bool(extract_project(url))


async def get_latest_nuget_package(src_uri: str, ebuild: str,
                                   settings: LivecheckSettings) -> tuple[str, str]:
    """
    Get the latest version of a NuGet package from its source URI.

    Parameters
    ----------
    src_uri : str
        Source URI from the ebuild ``SRC_URI``.
    ebuild : str
        Ebuild atom string for version-selection context.
    settings : LivecheckSettings
        Livecheck configuration.

    Returns
    -------
    tuple[str, str]
        Latest version string and matching package download URL, or two empty strings if not found.
    """
    project_name = extract_project(src_uri)
    if not project_name:
        return '', ''
    return await _get_latest_nuget_package(project_name, ebuild, settings)


async def get_latest_nuget_metadata(remote: str, ebuild: str,
                                    settings: LivecheckSettings) -> tuple[str, str]:
    """
    Get the latest version of a NuGet package using metadata.

    Parameters
    ----------
    remote : str
        NuGet package identifier from ebuild metadata.
    ebuild : str
        Ebuild atom string for version-selection context.
    settings : LivecheckSettings
        Livecheck configuration.

    Returns
    -------
    tuple[str, str]
        Latest version string and matching package download URL, or two empty strings if not found.
    """
    return await _get_latest_nuget_package(remote.lower(), ebuild, settings)


async def _get_latest_nuget_package(package_id: str, ebuild: str,
                                    settings: LivecheckSettings) -> tuple[str, str]:
    catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)
    url = NUGET_DOWNLOAD_URL % package_id
    if not (response := await get_content(url)):
        return '', ''
    payload = response.json()
    versions = payload.get('versions') or []
    results: list[dict[str, str]] = [{
        'tag': v
    } for v in versions if settings.is_devel(catpkg) or '-' not in v]
    if last_version := get_last_version(results, package_id, ebuild, settings):
        version = last_version['version']
        download_url = (f'https://api.nuget.org/v3-flatcontainer/{package_id}/'
                        f'{version}/{package_id}.{version}.nupkg')
        return version, download_url
    return '', ''
