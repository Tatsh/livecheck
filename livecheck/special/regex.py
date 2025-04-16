import logging
import re

from defusedxml import ElementTree as ET  # noqa: N817

from livecheck.constants import RSS_NS
from livecheck.settings import LivecheckSettings
from livecheck.utils import get_content, is_sha
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

__all__ = ('get_latest_regex_package',)

logger = logging.getLogger(__name__)


def get_latest_regex_package(ebuild: str, url: str, regex: str,
                             settings: LivecheckSettings) -> tuple[str, str, str]:

    _, _, _, ebuild_version = catpkg_catpkgsplit(ebuild)

    if not (r := get_content(url)):
        return '', '', ''

    results: list[dict[str, str]] = []
    for result in re.findall(regex, r.text):
        if is_sha(result) and not results:
            logger.info('Found commit hash %s in %s.', result, url)
            hash_date = ''
            try:
                updated_el = ET.fromstring(r.text).find('entry/updated', RSS_NS)
                assert updated_el is not None
                assert updated_el.text is not None
                if re.search(r'(2[0-9]{7})', ebuild_version):
                    hash_date = updated_el.text.split('T')[0].replace('-', '')
                    logger.debug('Use updated date %s for commit %s.', hash_date, result)
            except ET.ParseError:
                logger.exception('Error parsing %s.', url)
            return result, hash_date, url
        results.append({'tag': result})

    if last_version := get_last_version(results, '', ebuild, settings):
        return last_version['version'], '', ''

    return '', '', ''
