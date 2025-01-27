from pathlib import Path
import logging
import re

from .utils import EbuildTempFile
from ..utils import get_content

__all__ = ('update_go_ebuild',)

logger = logging.getLogger(__name__)


class InvalidGoSumURITemplate(ValueError):
    def __init__(self) -> None:
        super().__init__('URI template missing @PV@ or @SHA@.')


def update_go_ebuild(ebuild: str, version: str, go_sum_uri_template: str) -> None:
    if '@PV@' not in go_sum_uri_template and '@SHA@' not in go_sum_uri_template:
        raise InvalidGoSumURITemplate
    sha = ''
    try:
        if (first_match := [
                re.match(r'^SHA="([^"]+)"', x)
                for x in Path(ebuild).read_text(encoding='utf-8').splitlines()
        ][0]):
            sha = first_match.group(1)
    except IndexError:
        pass
    uri = go_sum_uri_template.replace('@PV@', version).replace('@SHA@', sha)
    if not (r := get_content(uri)):
        return
    new_ego_sum_lines = (f'"{line}"'
                         for line in (re.sub(r' h1\:.*$', '', x) for x in r.text.splitlines()))
    with EbuildTempFile(ebuild) as temp_file:
        with temp_file.open('w', encoding='utf-8') as tf:
            updated = False
            found_closing_bracket = False
            with Path(ebuild).open('r', encoding='utf-8') as f:
                for line in f.readlines():
                    if line.startswith('EGO_SUM=(') and not updated:
                        logger.debug('Found EGO_SUM=( line.')
                        tf.write('EGO_SUM=(\n')
                        logger.debug('Writing new EGO_SUM content.')
                        for pkg in new_ego_sum_lines:
                            tf.write(f'\t{pkg}\n')
                        tf.write(')\n')
                        updated = True
                    elif updated and not found_closing_bracket:
                        if line.strip() == ')':
                            logger.debug('Found closing bracket for EGO_SUM.')
                            found_closing_bracket = True
                    else:
                        tf.write(line)
