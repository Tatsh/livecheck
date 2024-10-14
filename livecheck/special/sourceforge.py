import requests
import re

from http import HTTPStatus
from loguru import logger

__all__ = ("get_latest_sourceforge_package",)


def get_latest_sourceforge_package(project_name: str) -> tuple[str, str]:
    url = f"https://sourceforge.net/projects/{project_name}/best_release.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        if response.status_code == HTTPStatus.OK:
            release_json = response.json()

            release = release_json.get('release')
            if release and release.get('filename'):
                filename = release['filename']
                version_match = re.search(r'/(\d+\.\d+\.\d+)/', filename)

                if version_match:
                    version = version_match.group(1)
                    download_url = f"https://downloads.sourceforge.net/{project_name}/{project_name}-{version}.tar.gz"
                    return version, download_url
        else:
            logger.debug(f"Project not found: {url}")

    except requests.exceptions.JSONDecodeError as e:
        logger.debug(f"Error decoding JSON {url}: {e}")
    except requests.exceptions.HTTPError as e:
        logger.debug(f"Error accessing the URL: {e}")

    return '', ''
