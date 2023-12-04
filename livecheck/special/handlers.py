import logging
import re
import xml.etree.ElementTree as etree

import requests

from ..constants import RSS_NS
from ..utils import assert_not_none

logger = logging.getLogger(__name__)


def handle_glabels(s: str) -> str:
    r = requests.get(f'https://github.com/jimevins/glabels-qt/commits/glabels-{s}.atom', timeout=30)
    r.raise_for_status()
    return ('3.99_p' + assert_not_none(
        assert_not_none(etree.fromstring(r.text).find('entry/updated',
                                                      RSS_NS)).text).split('T')[0].replace('-', ''))


def handle_re(s: str) -> str:
    return re.sub(r'^re(3|VC|LCS)_v?', '', s)


def handle_cython_post_suffix(s: str) -> str:
    return s.replace('.post', '.')


OUTFOX_MAXSPLIT = 2


def handle_outfox(s: str) -> str:
    x = re.split(r'-pre(?:0+)?', s, maxsplit=OUTFOX_MAXSPLIT)
    if len(x) == OUTFOX_MAXSPLIT:
        return f'{x[0]}_p{x[1]}'
    return x[0]


def handle_outfox_serenity(s: str) -> str:
    return s.replace('s', '.')


def handle_bsnes_hd(s: str) -> str:
    logger.debug('handle_bsnes_hd() <- "%s"', s)
    major, minor = assert_not_none(re.match(r'^beta_(\d+)_(\d+(?:h\d+)?)', s)).groups()
    minor = re.sub(r'h\d+', '', minor)
    ret = f'{major}.{minor}_beta'
    logger.debug('handle_bsnes_hd() -> "%s"', ret)
    return ret


def handle_pl(s: str) -> str:
    logger.debug('handle_pl() < "%s"', s)
    major, minor, mm, pl = assert_not_none(re.match(r'^v?(\d+)\.(\d+)\.(\d+)-pl(\d+)', s)).groups()
    ret = f'{major}.{minor}.{mm}.{pl}'
    logger.debug('handle_pl() -> "%s"', ret)
    return ret
