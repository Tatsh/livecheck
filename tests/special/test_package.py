from typing import Any

from livecheck.special.package import extract_project, is_package
import pytest

test_cases = {
    'test_extract_project_npmjs_org': {
        'url': 'https://registry.npmjs.org/package-name',
        'expected': ('registry.npmjs.org', 'package-name'),
        'is_package': True
    },
    'test_extract_project_yarnpkg_com': {
        'url': 'https://registry.yarnpkg.com/package-name',
        'expected': ('registry.yarnpkg.com', 'package-name'),
        'is_package': True
    },
    'test_extract_project_scoped_package': {
        'url': 'https://registry.npmjs.org/@scope/package-name',
        'expected': ('registry.npmjs.org', '@scope/package-name'),
        'is_package': True
    },
    'test_extract_project_invalid_url': {
        'url': 'https://registry.npmjs.org/',
        'expected': ('', ''),
        'is_package': False
    },
    'test_extract_project_invalid_url2': {
        'url': 'https://aregistry.npmjs.org/package-name',
        'expected': ('', ''),
        'is_package': False
    },
    'test_extract_project_invalid_url3': {
        'url': 'https://registry.npmjs.com/package-name',
        'expected': ('', ''),
        'is_package': False
    },
    'test_extract_project_empty_string': {
        'url': '',
        'expected': ('', ''),
        'is_package': False
    },
    'devcontainers': {
        'url': 'https://registry.npmjs.org/@devcontainers/cli/-/cli-devcontainer-0.72.0.tgz',
        'expected': ('registry.npmjs.org', '@devcontainers/cli'),
        'is_package': True
    },
}


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_extract_project(test_case: dict[str, Any]) -> None:
    assert extract_project(test_case['url']) == test_case['expected']


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_is_package(test_case: dict[str, Any]) -> None:
    assert is_package(test_case['url']) == test_case['is_package']
