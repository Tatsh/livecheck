"""Special regular expression handling."""
from __future__ import annotations

from typing import TYPE_CHECKING
import logging
import re

from defusedxml import ElementTree as ET  # noqa: N817
from livecheck.constants import RSS_NS
from livecheck.utils import get_content, is_sha
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

if TYPE_CHECKING:
    from livecheck.settings import LivecheckSettings

__all__ = ('get_latest_regex_package',)

logger = logging.getLogger(__name__)


def get_latest_regex_package(ebuild: str, url: str, regex: str,
                             settings: LivecheckSettings) -> tuple[str, str, str]:
    """Get the latest version of a package using a regular expression."""
    _, _, _, ebuild_version = catpkg_catpkgsplit(ebuild)

    # Get custom request parameters from settings
    catpkg = catpkg_catpkgsplit(ebuild)[0]
    headers = settings.request_headers.get(catpkg, {})
    params = settings.request_params.get(catpkg, {})
    method = settings.request_method.get(catpkg, 'GET')
    data = settings.request_data.get(catpkg, {})
    multiline = settings.regex_multiline.get(catpkg, False)

    if not (r := get_content(url, headers=headers, params=params, method=method, data=data)):
        return '', '', ''

    results: list[dict[str, str]] = []
    # Use re.MULTILINE if multiline flag is set
    regex_flags = re.MULTILINE if multiline else 0
    for result in re.findall(regex, r.text, flags=regex_flags):
        if is_sha(result) and not results:
            logger.info('Found commit hash %s in %s.', result, url)
            hash_date = ''
            try:
                updated_el = ET.fromstring(r.text).find('entry/updated', RSS_NS)
            except ET.ParseError:
                logger.debug('Ignoring XML parse error (URL: %s).', url)
                continue
            assert updated_el is not None
            assert updated_el.text is not None
            if re.search(r'(2[0-9]{7})', ebuild_version):
                hash_date = updated_el.text.split('T')[0].replace('-', '')
                logger.debug('Using updated date %s for commit %s.', hash_date, result)
            return result, hash_date, url
        results.append({'tag': result})

    if last_version := get_last_version(results, '', ebuild, settings):
        return last_version['version'], '', ''

    return '', '', ''
