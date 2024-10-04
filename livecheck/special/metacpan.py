import requests

from loguru import logger

__all__ = ("def get_latest_metacpan_package",)


def get_latest_metacpan_package(package_name: str) -> tuple[str, str]:
    api_url = f"https://fastapi.metacpan.org/v1/release/{package_name}"

    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Lanza un error si la solicitud falla

        release_info = response.json()

        latest_version = release_info.get('version')
        download_url = release_info.get('download_url')

        if latest_version and download_url:
            return latest_version, download_url

        logger.debug(f"Version information not found for {package_name}.")

    except requests.exceptions.HTTPError as e:
        logger.debug(f"Error accessing the URL: {e}")

    return '', ''
