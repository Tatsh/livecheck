from __future__ import annotations

from typing import TYPE_CHECKING, Any

from livecheck.special.metacpan import (
    extract_perl_package,
    get_latest_metacpan_metadata,
    get_latest_metacpan_package,
    is_metacpan,
)
import pytest

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from pytest_mock import MockerFixture

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


@pytest.mark.parametrize(
    ('url', 'ebuild', 'api_hits', 'api_release', 'expected_version'),
    [
        (
            'https://metacpan.org/release/Foo-Bar-1.23',
            'foo-bar.ebuild',
            [{
                '_source': {
                    'version': '1.23'
                }
            }, {
                '_source': {
                    'version': '1.22'
                }
            }],
            {
                'version': '1.23'
            },
            '1.23',
        ),
        (
            'https://metacpan.org/release/Foo-Bar-2.00',
            'foo-bar.ebuild',
            [],
            {
                'version': '2.00'
            },
            '2.00',
        ),
        (
            'https://metacpan.org/release/Foo-Bar-3.00',
            'foo-bar.ebuild',
            [],
            {},
            '',
        ),
    ],
)
def test_get_latest_metacpan_package(mocker: MockerFixture, url: str, ebuild: str,
                                     api_hits: Collection[Any], api_release: Mapping[str, Any],
                                     expected_version: str) -> None:
    def fake_get_content(url_arg: str) -> Any:
        class FakeResponse:
            def json(self) -> Any:  # noqa: PLR6301
                if 'release/_search' in url_arg:
                    return {'hits': {'hits': api_hits}}
                return api_release

        if not api_hits and not api_release:
            return None
        return FakeResponse()

    def fake_get_last_version(results: Sequence[Any], package_name: str, ebuild: str,
                              settings: Any) -> dict[str, str] | None:
        if not results or (not results[-1].get('tag') and not results[-1].get('version')):
            return None
        last = results[-1]
        return {'version': last.get('tag') or last.get('version')}

    mocker.patch('livecheck.special.metacpan.get_content', side_effect=fake_get_content)
    mocker.patch('livecheck.special.metacpan.get_last_version', side_effect=fake_get_last_version)
    settings = mocker.Mock()
    result = get_latest_metacpan_package(url, ebuild, settings)
    assert result == expected_version


@pytest.mark.parametrize(
    ('remote', 'ebuild', 'api_hits', 'api_release', 'expected_version'),
    [
        (
            'Foo-Bar',
            'foo-bar.ebuild',
            [{
                '_source': {
                    'version': '1.50'
                }
            }, {
                '_source': {
                    'version': '1.40'
                }
            }],
            {
                'version': '1.50'
            },
            '1.50',
        ),
        (
            'Baz-Quux',
            'baz-quux.ebuild',
            [],
            {
                'version': '2.10'
            },
            '2.10',
        ),
        (
            'NoVersion',
            'no-version.ebuild',
            [],
            {},
            '',
        ),
    ],
)
def test_get_latest_metacpan_metadata(mocker: MockerFixture, remote: str, ebuild: str,
                                      api_hits: Collection[Any], api_release: Mapping[str, Any],
                                      expected_version: str) -> None:
    def fake_get_content(url_arg: str) -> Any:
        class FakeResponse:
            def json(self) -> Any:  # noqa: PLR6301
                if 'release/_search' in url_arg:
                    return {'hits': {'hits': api_hits}}
                return api_release

        if not api_hits and not api_release:
            return None
        return FakeResponse()

    def fake_get_last_version(results: Sequence[Any], package_name: str, ebuild: str,
                              settings: Any) -> dict[str, str] | None:
        if not results or (not results[-1].get('tag') and not results[-1].get('version')):
            return None
        last = results[-1]
        return {'version': last.get('tag') or last.get('version')}

    mocker.patch('livecheck.special.metacpan.get_content', side_effect=fake_get_content)
    mocker.patch('livecheck.special.metacpan.get_last_version', side_effect=fake_get_last_version)
    settings = mocker.Mock()
    result = get_latest_metacpan_metadata(remote, ebuild, settings)
    assert result == expected_version
