"""Golang functions."""
from __future__ import annotations

from pathlib import Path
import contextlib
import logging
import re

from livecheck.utils import get_content

from .utils import EbuildTempFile

__all__ = ('update_go_ebuild',)

logger = logging.getLogger(__name__)


class InvalidGoSumURITemplate(ValueError):
    """Raised when the Go sum URI template is invalid."""
    def __init__(self) -> None:
        super().__init__('URI template missing @PV@ or @SHA@.')


def update_go_ebuild(ebuild: str, version: str, go_sum_uri_template: str) -> None:
    """
    Update a Go ebuild with the latest EGO_SUM content.

    Raises
    ------
    InvalidGoSumURITemplate
        If the URI template does not contain '@PV@' or '@SHA@'.
    """
    if '@PV@' not in go_sum_uri_template and '@SHA@' not in go_sum_uri_template:
        raise InvalidGoSumURITemplate
    sha = ''
    with contextlib.suppress(StopIteration):
        if (first_match :=
                next(y for y in (re.match(r'^SHA="([^"]+)"', x)
                                 for x in Path(ebuild).read_text(encoding='utf-8').splitlines())
                     if y is not None)):
            sha = first_match.group(1)
    uri = go_sum_uri_template.replace('@PV@', version).replace('@SHA@', sha)
    if not (r := get_content(uri)):
        return
    # Filter out /go.mod lines and strip hash part.
    new_ego_sum_lines = []
    for line in r.text.splitlines():
        # Skip empty lines.
        if not line.strip():
            continue
        # Skip /go.mod entries
        if '/go.mod' in line:
            continue
        # Remove hash part (e.g., " h1:..." or " h256:...")
        cleaned = re.sub(r' h\d+:.*$', '', line).strip()
        if cleaned:
            new_ego_sum_lines.append(f'"{cleaned}"')

    with EbuildTempFile(ebuild) as temp_file, temp_file.open('w', encoding='utf-8') as tf:
        updated = False
        found_closing_bracket = False
        with Path(ebuild).open('r', encoding='utf-8') as f:
            for line in f:
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
