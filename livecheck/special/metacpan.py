from urllib.parse import urlparse
import re

from ..settings import LivecheckSettings
from ..utils import get_content
from ..utils.portage import get_last_version

__all__ = ("get_latest_metacpan_package", "is_metacpan", "METACPAN_METADATA",
           "get_latest_metacpan_metadata")

METACPAN_METADATA = 'cpan'


def extract_perl_package(path: str) -> str:
    match = re.search(r'/([^/]+)-[\d.]+\.*', path)
    return match.group(1) if match else ''


def get_latest_metacpan_package(path: str, ebuild: str, settings: LivecheckSettings) -> str:
    package_name = extract_perl_package(path)
    return get_latest_metacpan_package2(package_name, ebuild, settings)


def get_latest_metacpan_package2(package_name: str, ebuild: str,
                                 settings: LivecheckSettings) -> str:
    results: list[dict[str, str]] = []
    if r := get_content(
            f"https://fastapi.metacpan.org/v1/release/_search?q=distribution:{package_name}"):
        for hit in r.json().get("hits", {}).get("hits", []):
            results.extend([{"tag": hit["_source"]["version"]}])

    # Many times it does not exist as in the previous list,
    # that is why the latest version is checked again.
    if r := get_content(f"https://fastapi.metacpan.org/v1/release/{package_name}"):
        results.append({"tag": r.json().get('version')})

    last_version = get_last_version(results, package_name, ebuild, settings)
    if last_version:
        return last_version['version']

    return ''


def is_metacpan(url: str) -> bool:
    return urlparse(url).netloc in {'metacpan.org', 'cpan'}


def get_latest_metacpan_metadata(remote: str, ebuild: str, settings: LivecheckSettings) -> str:
    return get_latest_metacpan_package2(remote, ebuild, settings)
