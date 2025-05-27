from __future__ import annotations

from typing import Any

from livecheck.special.metacpan import extract_perl_package, is_metacpan
import pytest

test_cases = {
    'valid_url': {
        'url': 'https://metacpan.org/release/Foo-Bar-1.23',
        'expected': 'Foo-Bar',
        'is_metacpan': True
    },
    'valid_url_with_version': {
        'url': 'https://metacpan.org/release/Foo-Bar-1.23.tar.gz',
        'expected': 'Foo-Bar',
        'is_metacpan': True
    },
    'invalid_url': {
        'url': 'https://example.com/release/Foo-Bar-1.23',
        'expected': '',
        'is_metacpan': False
    },
    'invalid_url_no_version': {
        'url': 'https://metacpan.org/release/Foo-Bar',
        'expected': '',
        'is_metacpan': False
    },
    'cpan_url': {
        'url': 'mirror://cpan/release/Foo-Bar-1.23',
        'expected': 'Foo-Bar',
        'is_metacpan': True
    },
    'cpan_url_no_version': {
        'url': 'mirror://cpan/release/Foo-Bar',
        'expected': '',
        'is_metacpan': False
    },
    'net-mail/grepmail': {
        'url': 'mirror://cpan/authors/id/D/DC/DCOPPIT/grepmail-5.3111.tar.gz',
        'expected': 'grepmail',
        'is_metacpan': True
    },
}


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_extract_perl_package(test_case: dict[str, Any]) -> None:
    assert extract_perl_package(test_case['url']) == test_case['expected']


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_is_metacpan(test_case: dict[str, Any]) -> None:
    assert is_metacpan(test_case['url']) == test_case['is_metacpan']
