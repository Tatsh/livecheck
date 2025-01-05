import json
import urllib.request
import urllib.error
from loguru import logger

__all__ = ("get_latest_davinci_package")


def get_latest_davinci_package(pkg: str) -> str:
    api_url = f"https://www.blackmagicdesign.com/api/support/latest-stable-version/{pkg}/linux"

    try:
        with urllib.request.urlopen(api_url) as response:
            if response.status != 200:
                logger.error(f"Request failed with status code: {response.status}")
            else:
                data = json.load(response)
                return f"{data['linux']['major']}.{data['linux']['minor']}.{data['linux']['releaseNum']}"
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        logger.error(f"URL error: {e.reason}")
    except (json.JSONDecodeError, KeyError):
        logger.error("Error parsing JSON or missing required fields")
    return ''
