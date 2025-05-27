from __future__ import annotations

from typing import Any

from livecheck.special.gitlab import extract_domain_and_namespace, is_gitlab
import pytest

test_cases = {
    'valid_gitlab_url': {
        'url': 'https://gitlab.com/group/project',
        'expected': ('gitlab.com', 'group/project', 'project'),
        'is_gitlab': True
    },
    'invalid_gitlab_url': {
        'url': 'https://notgitlab.com/group/project',
        'expected': ('', '', ''),
        'is_gitlab': False
    },
    'invalid_gitlab_url2': {
        'url': 'https://gitlab.com',
        'expected': ('', '', ''),
        'is_gitlab': False
    },
    'invalid_gitlab_url3': {
        'url': 'https://gitlab.com/group/',
        'expected': ('', '', ''),
        'is_gitlab': False
    },
    'gitlab_es_url': {
        'url': 'https://gitlab.es/group/project',
        'expected': ('', '', ''),
        'is_gitlab': False
    },
    'example_gitlab_url': {
        'url': 'https://example.gitlab.com/group/project',
        'expected': ('', '', ''),
        'is_gitlab': False
    },
    'gitlab_example_url': {
        'url': 'https://gitlab.example.com/group/project',
        'expected': ('gitlab.example.com', 'group/project', 'project'),
        'is_gitlab': True
    },
    'example_com_url': {
        'url': 'https://example.com/group/project',
        'expected': ('', '', ''),
        'is_gitlab': False
    },
    'gitlab_merge_request_url': {
        'url': 'https://gitlab.com/group/project/-/merge_requests',
        'expected': ('gitlab.com', 'group/project', 'project'),
        'is_gitlab': True
    },
    'gitlab_subgroup_url': {
        'url': 'https://gitlab.com/group/subgroup/project',
        'expected': ('gitlab.com', 'group/subgroup/project', 'project'),
        'is_gitlab': True
    },
    'sys-apps/udev-usb-sync': {
        'url': 'https://gitlab.manjaro.org/fhdk/udev-usb-sync',
        'expected': ('gitlab.manjaro.org', 'fhdk/udev-usb-sync', 'udev-usb-sync'),
        'is_gitlab': True
    },
    'x11-misc/xdg-utils': {
        'url':
            'https://gitlab.freedesktop.org/xdg/xdg-utils/-/archive/v1.2.1/xdg-utils-1.2.1.tar.bz2',
        'expected': ('gitlab.freedesktop.org', 'xdg/xdg-utils', 'xdg-utils'),
        'is_gitlab':
            True
    },
}


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_extract_domain_and_namespace(test_case: dict[str, Any]) -> None:
    assert extract_domain_and_namespace(test_case['url']) == test_case['expected']


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_is_gitlab(test_case: dict[str, Any]) -> None:
    assert is_gitlab(test_case['url']) == test_case['is_gitlab']
