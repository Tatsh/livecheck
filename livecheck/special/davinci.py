import json
import requests
from loguru import logger

__all__ = ("get_latest_davinci_package")


def get_latest_davinci_package(pkg: str) -> str:
    api_url = f"https://www.blackmagicdesign.com/api/support/latest-stable-version/{pkg}/linux"

    try:
        r = requests.get(api_url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return f"{data['linux']['major']}.{data['linux']['minor']}.{data['linux']['releaseNum']}"
    except requests.exceptions.HTTPError as e:
        logger.error(f"URL error: {e}")
    except (json.JSONDecodeError, KeyError):
        logger.error("Error parsing JSON or missing required fields")
    return ''
