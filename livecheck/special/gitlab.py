import requests
import re
from urllib.parse import urlparse, quote
from datetime import datetime
from loguru import logger

from ..utils.portage import is_version_development

__all__ = ("get_latest_gitlab_package")

# Number of versions to fetch from GitLab
VERSIONS = 40


def extract_domain_and_namespace(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path.strip('/')
    if '/-/' in path:
        path = path.split('/-/')[0]

    return domain, path


def get_latest_gitlab_package(url: str,
                              development: bool = False,
                              restrict_version: str = '') -> tuple[str, str, str]:

    domain, path_with_namespace = extract_domain_and_namespace(url)
    base_api_url = f"https://{domain}/api/v4"
    encoded_path = quote(path_with_namespace, safe='')
    try:
        tags_response = requests.get(
            f"{base_api_url}/projects/{encoded_path}/repository/tags?per_page={VERSIONS}")
        tags_response.raise_for_status()
        tags_data = tags_response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"URL error: {e}")
        return '', '', ''

    results = []
    for tag in tags_data:
        original_name = tag.get("name", "")
        cleaned_name = re.sub(r"^[^\d]+", "", original_name)
        match = re.match(r"^(\d+(?:\.\d+){0,2})", cleaned_name)
        if match:
            cleaned_name = match.group(1)

        date_str = tag.get("commit", {}).get("created_at", "")
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            formatted_date = dt.strftime("%Y%m%d")
        except:
            formatted_date = date_str[:10]

        results.append({
            "tag": cleaned_name,
            "id": tag.get("commit", {}).get("id", ""),
            "date": formatted_date
        })

    for result in results:
        version = result["tag"]
        if not version.startswith(restrict_version):
            continue
        if not is_version_development(version) or development:
            return version, result["id"], result["date"]

    logger.debug('No updated hash found')
    return '', '', ''
