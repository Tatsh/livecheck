from typing import Any

import pytest

from livecheck.special.bitbucket import extract_workspace_and_repository, is_bitbucket

test_cases = {
    "atlassian": {
        "url": "https://bitbucket.org/atlassian/python-bitbucket",
        "expected": ("atlassian", "python-bitbucket"),
        "is_bitbucket": True
    },
    "atlassian_master": {
        "url": "https://bitbucket.org/atlassian/python-bitbucket/src/master/",
        "expected": ("atlassian", "python-bitbucket"),
        "is_bitbucket": True
    },
    "bad_url": {
        "url": "https://bitbucket.org/",
        "expected": ("", ""),
        "is_bitbucket": False
    },
    "bad_url2": {
        "url": "https://github.io/username/repo.git",
        "expected": ("", ""),
        "is_bitbucket": False
    },
    "bad_url3": {
        "url": "https://bitbucket.org/atlassian/",
        "expected": ("", ""),
        "is_bitbucket": False
    },
    "bitbucket_repo_git": {
        "url": "https://bitbucket.org/atlassian/python-bitbucket.git",
        "expected": ("atlassian", "python-bitbucket"),
        "is_bitbucket": True
    },
    "media-plugins/vdr-dvbhddevice": {
        "url": "https://bitbucket.org/powARman/dvbhddevice/get/20170225.tar.bz2",
        "expected": ("powARman", "dvbhddevice"),
        "is_bitbucket": True
    },
}


@pytest.mark.parametrize("test_case", test_cases.values(), ids=test_cases.keys())
def test_extract_owner_repo(test_case: dict[str, Any]) -> None:
    assert extract_workspace_and_repository(test_case["url"]) == test_case["expected"]


@pytest.mark.parametrize("test_case", test_cases.values(), ids=test_cases.keys())
def test_is_github(test_case: dict[str, Any]) -> None:
    assert is_bitbucket(test_case["url"]) == test_case["is_bitbucket"]
