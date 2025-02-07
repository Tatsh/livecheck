from pathlib import Path
from urllib.parse import urljoin, urlparse
import re

from bs4 import BeautifulSoup

from ..settings import LivecheckSettings
from ..utils import get_content
from ..utils.portage import get_last_version
from .utils import get_archive_extension

__all__ = ("get_latest_directory_package",)


def get_latest_directory_package(url: str, ebuild: str, settings: LivecheckSettings) -> str:
    if m := re.search(r'^(.*?)(?=-\d)', Path(url).name):
        directory = re.sub(r'/[^/]+$', '', url) + '/'
        if not (r := get_content(directory)):
            return ''

        archive = m.group(1).strip()

        results: list[dict[str, str]] = []
        for item in BeautifulSoup(r.text, 'html.parser').find_all('a', href=True):
            if (href := item["href"]) and get_archive_extension(href):
                file = urlparse(urljoin(directory, href)).path
                name = Path(file).name
                if name.startswith(archive):
                    results.append({"tag": name})

        if last_version := get_last_version(results, archive, ebuild, settings):
            return last_version['version']

    return ''
