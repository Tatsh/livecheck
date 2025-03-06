from typing import Any

import pytest

from livecheck.special.github import extract_owner_repo, is_github

test_cases = {
    "test_extract_owner_repo_valid_github_com": {
        "url": "https://github.com/username/repo",
        "expected": ("https://github.com/username/repo", "username", "repo"),
        "is_github": True
    },
    "test_extract_owner_repo_valid_github_io": {
        "url": "https://username.github.io/repo",
        "expected": ("https://username.github.io/repo", "username", "repo"),
        "is_github": True
    },
    "test_extract_owner_repo_invalid_url": {
        "url": "https://example.com/username/repo",
        "expected": ("", "", ""),
        "is_github": False
    },
    "test_extract_owner_repo_no_repo": {
        "url": "https://github.com/username/",
        "expected": ("", "", ""),
        "is_github": False
    },
    "test_extract_owner_repo_empty_string": {
        "url": "",
        "expected": ("", "", ""),
        "is_github": False
    },
    "test_extract_owner_repo_github_com_with_dot_git": {
        "url": "https://github.io/username/repo.git",
        "expected": ("https://github.io/username/repo", "username", "repo"),
        "is_github": True
    },
    "test_extract_owner_repo_github_com_with_subpath": {
        "url": "https://github.com/username/repo/subpath",
        "expected": ("https://github.com/username/repo", "username", "repo"),
        "is_github": True
    },
    "test_extract_owner_repo_github_com_with_query_params": {
        "url": "https://github.com/username/repo?param=value",
        "expected": ("https://github.com/username/repo", "username", "repo"),
        "is_github": True
    },
    "test_extract_owner_repo_github_com_with_fragment": {
        "url": "https://github.com/username/repo#section",
        "expected": ("https://github.com/username/repo", "username", "repo"),
        "is_github": True
    },
    "test_extract_owner_repo_invalid_url2": {
        "url": "https://github.org/username/repo.git",
        "expected": ("", "", ""),
        "is_github": False
    },
    "test_extract_owner_repo_invalid_url3": {
        "url": "https://github.com",
        "expected": ("", "", ""),
        "is_github": False
    },
    "www-apps/icingaweb2": {
        "url": "https://codeload.github.com/Icinga/icingaweb2/tar.gz/v2.9.0",
        "expected": ("https://codeload.github.com/Icinga", "codeload", "Icinga"),
        "is_github": True
    },
    "net-libs/neon": {
        "url": "https://notroj.github.io/neon/neon-0.33.0.tar.gz",
        "expected": ("https://notroj.github.io/neon", "notroj", "neon"),
        "is_github": True
    },
}


@pytest.mark.parametrize("test_case", test_cases.values(), ids=test_cases.keys())
def test_extract_owner_repo(test_case: dict[str, Any]) -> None:
    assert extract_owner_repo(test_case["url"]) == test_case["expected"]


@pytest.mark.parametrize("test_case", test_cases.values(), ids=test_cases.keys())
def test_is_github(test_case: dict[str, Any]) -> None:
    assert is_github(test_case["url"]) == test_case["is_github"]
