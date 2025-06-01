"""Directory functions."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse
import re

from bs4 import BeautifulSoup
from livecheck.utils import get_content
from livecheck.utils.portage import get_last_version

from .utils import get_archive_extension

if TYPE_CHECKING:
    from livecheck.settings import LivecheckSettings

__all__ = ('get_latest_directory_package',)


def get_latest_directory_package(url: str, ebuild: str,
                                 settings: LivecheckSettings) -> tuple[str, str]:
    """Get the latest version of a package from a directory listing."""
    if m := re.search(r'^(.*?)(?=-\d)', Path(url).name):
        directory = re.sub(r'/[^/]+$', '', url) + '/'
        if not (r := get_content(directory)):
            return '', ''

        archive = m.group(1).strip()

        results: list[dict[str, str]] = []
        for item in BeautifulSoup(r.text, 'html5lib').find_all('a', href=True):
            if (href := item['href']) and get_archive_extension(href):
                file = urlparse(urljoin(directory, href)).path
                name = Path(file).name
                if name.startswith(archive):
                    results.append({'tag': name, 'url': file})

        if last_version := get_last_version(results, archive, ebuild, settings):
            return last_version['version'], last_version['url']

    return '', ''
