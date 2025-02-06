from pathlib import Path
from urllib.parse import urljoin, urlparse
import os
import re
import xml.etree.ElementTree as etree

from ..settings import LivecheckSettings
from ..utils import get_content
from ..utils.portage import get_last_version

__all__ = ("get_latest_directory_package",)


def get_latest_directory_package(url: str, ebuild: str, settings: LivecheckSettings) -> str:
    # remove archive from the url
    directory = re.sub(r'/[^/]+$', '', url)

    # get archive from the url
    repository = Path(url).name

    if not (r := get_content(directory)):
        return ''

    if m := re.search(r'^(.*?)(?=-\d)', repository):
        archive = m.group(1).strip()
    else:
        return ''

    results: list[dict[str, str]] = []
    # get all tags a from the directory in xml format and check if a href is a start with name

    for item in etree.fromstring(r.text).findall(".//a"):
        if href := item.get("href"):
            link = urljoin(url, href)
            file = urlparse(link).path
            name = os.path.basename(file)
            if name.startswith(archive):
                # remove name from the file
                version = name[len(archive) + 1:]
                results.append({"tag": version})

    if last_version := get_last_version(results, repository, ebuild, settings):
        return last_version['version']

    return ''
