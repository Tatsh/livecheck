from __future__ import annotations

from typing import Any

from livecheck.special.gist import extract_id, is_gist
import pytest

test_cases = {
    'test_extract_id_github_com': {
        'url': 'https://gist.github.com/username/abcdef1234567890',
        'expected': 'abcdef1234567890',
        'gist': True
    },
    'test_extract_id_githubusercontent_com': {
        'url': 'https://gist.githubusercontent.com/username/abcdef1234567890/raw/filename',
        'expected': 'abcdef1234567890',
        'gist': True
    },
    'test_extract_id_invalid_url': {
        'url': 'https://example.com/username/abcdef1234567890',
        'expected': '',
        'gist': False
    },
    'test_extract_id_no_id': {
        'url': 'https://gist.github.com/username/',
        'expected': '',
        'gist': False
    },
    'test_extract_id_empty_string': {
        'url': '',
        'expected': '',
        'gist': False
    },
    'test_ntasos': {
        'url': 'https://gist.github.com/ntasos/8d1c7e2d2f8f5f1f3c9f',
        'expected': '8d1c7e2d2f8f5f1f3c9f',
        'gist': True
    },
    'test_bitrock': {
        'url':
            'https://gist.githubusercontent.com/mickael9/0b902da7c13207d1b86e/raw/ef65b6583c5cf077fb897a9a028781f577fed9ac/bitrock-unpacker.tcl',
        'expected':
            '0b902da7c13207d1b86e',
        'gist':
            True
    },
}


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_extract_id(test_case: dict[str, str]) -> None:
    assert extract_id(test_case['url']) == test_case['expected']


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_is_gist(test_case: dict[str, Any]) -> None:
    assert is_gist(test_case['url']) == test_case['gist']
