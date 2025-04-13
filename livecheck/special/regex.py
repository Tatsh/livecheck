import re
import xml.etree.ElementTree as ET

from loguru import logger

from livecheck.constants import RSS_NS
from livecheck.settings import LivecheckSettings
from livecheck.utils import get_content, is_sha
from livecheck.utils.portage import catpkg_catpkgsplit, get_last_version

__all__ = ('get_latest_regex_package',)


def get_latest_regex_package(ebuild: str, url: str, regex: str,
                             settings: LivecheckSettings) -> tuple[str, str, str]:

    _, _, _, ebuild_version = catpkg_catpkgsplit(ebuild)

    if not (r := get_content(url)):
        return '', '', ''

    results: list[dict[str, str]] = []
    for result in re.findall(regex, r.text):
        if is_sha(result) and not results:
            logger.info(f'Found commit hash {result} in {url}')
            hash_date = ''
            try:
                updated_el = ET.fromstring(r.text).find('entry/updated', RSS_NS)
                assert updated_el is not None
                assert updated_el.text is not None
                if re.search(r'(2[0-9]{7})', ebuild_version):
                    hash_date = updated_el.text.split('T')[0].replace('-', '')
                    logger.debug(f'Use updated date {hash_date} for commit {result}')
            except ET.ParseError:
                logger.error(f'Error parsing {url}')
            return result, hash_date, url
        results.append({'tag': result})

    if last_version := get_last_version(results, '', ebuild, settings):
        return last_version['version'], '', ''

    return '', '', ''
