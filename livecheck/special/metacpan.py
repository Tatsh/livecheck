import requests

from loguru import logger

__all__ = ("def get_latest_metacpan_package",)


def get_latest_metacpan_package(package_name: str) -> str:
    api_url = f"https://fastapi.metacpan.org/v1/release/{package_name}"

    try:
        response = requests.get(api_url)
        response.raise_for_status()

        release_info = response.json()

        return str(release_info.get('version'))

    except requests.exceptions.HTTPError as e:
        logger.debug(f"Error accessing the URL: {e}")

    return ''
