from ..settings import LivecheckSettings
from ..utils import get_content
from ..utils.portage import catpkg_catpkgsplit, get_last_version

__all__ = ("get_latest_repology",)

REPOLOGY_DOWNLOAD_URL = 'https://repology.org/api/v1/project/%s'


def get_latest_repology(ebuild: str, settings: LivecheckSettings, package: str = '') -> str:
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
            results.extend([{"tag": release.get('version')}])

    if last_version := get_last_version(results, '', ebuild, settings):
        return last_version['version']

    return ''
