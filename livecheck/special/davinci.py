"""DaVinci functions."""
from __future__ import annotations

from livecheck.utils import get_content

__all__ = ('get_latest_davinci_package',)

DAVINCI_TAG_URL = 'https://www.blackmagicdesign.com/api/support/latest-stable-version/%s/linux'


def get_latest_davinci_package(pkg: str) -> str:
    """Get the latest version of a DaVinci package."""
    url = DAVINCI_TAG_URL % (pkg)

    if not (r := get_content(url)):
        return ''

    data = r.json()
    if data['linux']['releaseNum'] == 0:
        return f"{data['linux']['major']}.{data['linux']['minor']}"
    return f"{data['linux']['major']}.{data['linux']['minor']}.{data['linux']['releaseNum']}"
