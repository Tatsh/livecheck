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

        release = release_json.get('release')
        if release and (filename := release.get('filename')):
            if version_match := re.search(r'/(\d+(?:\.\d+)+)/', filename):
                download_url = release.get('url').rstrip('/download')
                return version_match.group(1), download_url
        else:
            logger.debug(f"Could not extract filename or release: {url}")

    except requests.exceptions.JSONDecodeError as e:
        logger.debug(f"Error decoding JSON {url}: {e}")
    except requests.exceptions.HTTPError as e:
        logger.debug(f"Error accessing the URL: {e}")
    except Exception as e:
        logger.debug(f"An unexpected error occurred: {e}")

    return '', ''
