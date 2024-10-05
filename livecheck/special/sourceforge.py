import requests
import re

from loguru import logger

__all__ = ("get_latest_sourceforge_package",)


def get_latest_sourceforge_package(project_name: str) -> tuple[str, str]:
    url = f"https://sourceforge.net/projects/{project_name}/best_release.json"
    try:
        response = requests.get(url)
        response.raise_for_status()

        release_json = response.json()

        filename = release_json['release']['filename']

        version_match = re.search(r'/(\d+\.\d+\.\d+)/', filename)

        if version_match:
            version = version_match.group(1)
            download_url = f"https://downloads.sourceforge.net/{project_name}/{project_name}-{version}.tar.gz"
            return version, download_url

    except requests.exceptions.HTTPError as e:
        logger.debug(f"Error accessing the URL: {e}")

    return '', ''
