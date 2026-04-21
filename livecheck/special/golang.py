"""Golang functions."""
from __future__ import annotations

import contextlib
import logging
import re

from anyio import Path as AnyioPath
from livecheck.utils import get_content

from .utils import EbuildTempFile

__all__ = ('update_go_ebuild',)

logger = logging.getLogger(__name__)


class InvalidGoSumURITemplate(ValueError):
    """Raised when the Go sum URI template is invalid."""
    def __init__(self) -> None:
        super().__init__('URI template missing @PV@ or @SHA@.')


async def update_go_ebuild(ebuild: str, version: str, go_sum_uri_template: str) -> None:
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
    ebuild_text = await AnyioPath(ebuild).read_text(encoding='utf-8')
    with contextlib.suppress(StopIteration):
        if (first_match := next(y for y in (re.match(r'^SHA="([^"]+)"', x)
                                            for x in ebuild_text.splitlines()) if y is not None)):
            sha = first_match.group(1)
    uri = go_sum_uri_template.replace('@PV@', version).replace('@SHA@', sha)
    if not (r := await get_content(uri)) or not r.text:
        return
    new_ego_sum_lines = []
    for line in r.text.splitlines():
        if not line.strip():
            continue
        if '/go.mod' in line:
            continue
        cleaned = re.sub(r' h\d+:.*$', '', line).strip()
        if cleaned:
            new_ego_sum_lines.append(f'"{cleaned}"')

    async with EbuildTempFile(ebuild) as temp_file:
        updated = False
        found_closing_bracket = False
        out: list[str] = []
        for line in ebuild_text.splitlines(keepends=True):
            if line.startswith('EGO_SUM=(') and not updated:
                logger.debug('Found EGO_SUM=( line.')
                out.append('EGO_SUM=(\n')
                logger.debug('Writing new EGO_SUM content.')
                out.extend(f'\t{pkg}\n' for pkg in new_ego_sum_lines)
                out.append(')\n')
                updated = True
            elif updated and not found_closing_bracket:
                if line.strip() == ')':
                    logger.debug('Found closing bracket for EGO_SUM.')
                    found_closing_bracket = True
            else:
                out.append(line)
        await AnyioPath(temp_file).write_text(''.join(out), encoding='utf-8')
