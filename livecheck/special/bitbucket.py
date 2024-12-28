import re
import requests

from loguru import logger

__all__ = ("get_latest_bitbucket_package",)

# doc: https://developer.atlassian.com/cloud/bitbucket/rest/api-group-downloads/#api-repositories-workspace-repo-slug-downloads-get
BITBUCKET_URL = 'https://bitbucket.org/api/2.0/%s/%s/downloads?pagelen=100'

MAX_ITERATIONS = 2


def get_latest_bitbucket_package(path: str) -> str:
    workspace, repository = path.split('/')[-2:]

    session = requests.Session()

    url = BITBUCKET_URL % (workspace, repository)
    versions = set()

    version_pattern = re.compile(r"(\d+(\.\d+){0,2}(-alpha|-beta)?)")
    iteration_count = 0

    while url and iteration_count < MAX_ITERATIONS:
        try:
            response = session.get(url)
            response.raise_for_status()
            data = response.json()

            for item in data.get("values", []):
                file_name = item["name"]
                match = version_pattern.search(file_name)
                if match:
                    versions.add(match.group(1))  # Add the found version to the set

            url = data.get('next')
            iteration_count += 1
        except requests.RequestException as e:
            logger.debug(f"Error accessing the URL: {e}")
            break

    return sorted(versions)[-1] if versions else ''
