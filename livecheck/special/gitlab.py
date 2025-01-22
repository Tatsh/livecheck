import re
from urllib.parse import urlparse, quote

from ..settings import LivecheckSettings
from ..utils.portage import get_last_version
from ..utils import get_content

__all__ = ("get_latest_gitlab_package",)

# Number of versions to fetch from GitLab
VERSIONS = 40


def extract_domain_and_namespace(url: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    if '/-/' in path:
        path = path.split('/-/')[0]

    return parsed.netloc, path, path.split('/')[-1]


def get_latest_gitlab_package(url: str, ebuild: str, development: bool, restrict_version: str,
                              settings: LivecheckSettings) -> tuple[str, str]:

    domain, path_with_namespace, repo = extract_domain_and_namespace(url)
    base_api_url = f"https://{domain}/api/v4"
    encoded_path = quote(path_with_namespace, safe='')

    tags_response = get_content(
        f"{base_api_url}/projects/{encoded_path}/repository/tags?per_page={VERSIONS}")
    if not tags_response:
        return '', ''

    results: list[dict[str, str]] = []
    for tag in tags_response.json():
        original_name = tag.get("name", "")
        cleaned_name = re.sub(r"^[^\d]+", "", original_name)
        match = re.match(r"^(\d+(?:\.\d+){0,2})", cleaned_name)
        if match:
            cleaned_name = match.group(1)

        results.append({
            "tag": cleaned_name,
            "id": tag.get("commit", {}).get("id", ""),
        })

    last_version = get_last_version(results, repo, ebuild, development, restrict_version, settings)
    if last_version:
        return last_version['version'], last_version["id"]

    return '', ''
