"""Very special handlers."""
from __future__ import annotations

from functools import lru_cache
import logging
import re

from livecheck.utils import assert_not_none

from .github import get_latest_github_commit2

logger = logging.getLogger(__name__)


@lru_cache
def handle_glabels(s: str) -> str:
    """Handle glabels-qt versioning."""
    _, hash_date = get_latest_github_commit2('jimevins', 'glabels-qt', 'master')
    if not hash_date:
        return s
    return '3.99_p' + hash_date


def handle_re(s: str) -> str:
    """Handle re3, reVC, and reLCS versioning."""
    return re.sub(r'^re(3|VC|LCS)_v?', '', s)


def handle_cython_post_suffix(s: str) -> str:
    """Handle Cython ``.post`` suffix."""
    return s.replace('.post', '.')


OUTFOX_MAXSPLIT = 2


def handle_outfox(s: str) -> str:
    """Handle Outfox versioning."""
    x = re.split(r'-pre(?:0+)?', s, maxsplit=OUTFOX_MAXSPLIT)
    if len(x) == OUTFOX_MAXSPLIT:
        return f'{x[0]}_p{x[1]}'
    return x[0]


def handle_outfox_serenity(s: str) -> str:
    """Handle Outfox Serenity versioning."""
    return s.replace('s', '.')


def handle_bsnes_hd(s: str) -> str:
    """Handle bsnes-hd versioning."""
    logger.debug('handle_bsnes_hd() <- "%s"', s)
    major, minor = assert_not_none(re.match(r'^beta_(\d+)_(\d+(?:h\d+)?)', s)).groups()
    minor = re.sub(r'h\d+', '', minor)
    ret = f'{major}.{minor}_beta'
    logger.debug('handle_bsnes_hd() -> "%s"', ret)
    return ret


def handle_pl(s: str) -> str:
    r"""Handle ``-pl\d+`` versioning."""
    logger.debug('handle_pl() < "%s"', s)
    res = re.match(r'^v?(\d+)\.(\d+)\.(\d+)-pl(\d+)', s)
    if not res:
        logger.debug('handle_pl() -> ""')
        return ''
    major, minor, mm, pl = res.groups()
    ret = f'{major}.{minor}.{mm}.{pl}'
    logger.debug('handle_pl() -> "%s"', ret)
    return ret
