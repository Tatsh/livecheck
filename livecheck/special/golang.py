from pathlib import Path
import logging
import re
import tempfile

import requests

__all__ = ('update_go_ebuild',)

logger = logging.getLogger(__name__)


class InvalidGoSumURITemplate(ValueError):
    def __init__(self) -> None:
        super().__init__('URI template missing @PV@ or @SHA@.')


def update_go_ebuild(ebuild: str | Path, pkg: str, version: str, go_sum_uri_template: str) -> None:
    ebuild = Path(ebuild)
    if '@PV@' not in go_sum_uri_template and '@SHA@' not in go_sum_uri_template:
        raise InvalidGoSumURITemplate
    sha = ''
    try:
        if (first_match :=
            [re.match(r'^SHA="([^"]+)"', x) for x in ebuild.read_text().splitlines()][0]):
            sha = first_match.group(1)
    except IndexError:
        pass
    uri = go_sum_uri_template.replace('@PV@', version).replace('@SHA@', sha)
    r = requests.get(uri)
    r.raise_for_status()
    new_ego_sum_lines = (f'"{line}"'
                         for line in (re.sub(r' h1\:.*$', '', x) for x in r.text.splitlines()))
    tf = tempfile.NamedTemporaryFile(mode='w',
                                     prefix=ebuild.stem,
                                     suffix=ebuild.suffix,
                                     delete=False,
                                     dir=ebuild.parent)
    updated = False
    found_closing_bracket = False
    with ebuild.open('r') as f:
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
    ebuild.unlink()
    Path(tf.name).rename(ebuild).chmod(0o0644)
