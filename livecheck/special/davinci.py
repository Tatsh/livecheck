from ..utils import get_content

__all__ = ["get_latest_davinci_package"]

DAVINCI_TAG_URL = 'https://www.blackmagicdesign.com/api/support/latest-stable-version/%s/linux'


def get_latest_davinci_package(pkg: str) -> str:
    url = DAVINCI_TAG_URL % (pkg)

    if not (r := get_content(url)):
        return ''

    data = r.json()
    return f"{data['linux']['major']}.{data['linux']['minor']}.{data['linux']['releaseNum']}"
