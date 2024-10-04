from cgi import print_form
import requests

from loguru import logger

__all__ = ("get_latest_rubygems_package",)


def get_latest_rubygems_package(gem_name: str) -> tuple[str, str]:
    api_url = f"https://rubygems.org/api/v1/gems/{gem_name}.json"

    try:
        response = requests.get(api_url)
        response.raise_for_status()

        gem_info = response.json()

        latest_version = gem_info['version']
        download_url = f"https://rubygems.org/downloads/{gem_name}-{latest_version}.gem"

        return latest_version, download_url

    except requests.RequestException as e:
        logger.debug(f"Error accessing the URL: {e}")

    return '', ''
