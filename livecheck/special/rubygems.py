import requests

from loguru import logger

__all__ = ("get_latest_rubygems_package",)


def get_latest_rubygems_package(gem_name: str) -> str:
    api_url = f"https://rubygems.org/api/v1/gems/{gem_name}.json"

    try:
        response = requests.get(api_url)
        response.raise_for_status()

        gem_info = response.json()

        latest_version = gem_info['version']

        return latest_version

    except requests.RequestException as e:
        logger.debug(f"Error accessing the URL: {e}")

    return ''
