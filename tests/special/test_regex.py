from __future__ import annotations

from typing import TYPE_CHECKING

from defusedxml import ElementTree as ET  # noqa: N817
from livecheck.special.regex import get_latest_regex_package

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_latest_regex_package_no_content(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.regex.get_content', return_value=None)
    result = get_latest_regex_package('cat/pkg-1.0', 'http://example.com', r'.*', mocker.Mock())
    assert result == ('', '', '')


def test_get_latest_regex_package_commit_hash_found(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.regex.catpkg_catpkgsplit',
                 return_value=('cat', 'pkg', '', '20240601'))
    mock_response = mocker.Mock()
    mock_response.text = '<entry><id>abc123</id><updated>2024-06-01T12:00:00Z</updated></entry>'
    mocker.patch('livecheck.special.regex.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.regex.is_sha', return_value=True)
    mocker.patch('livecheck.special.regex.ET.fromstring',
                 return_value=mocker.Mock(find=mocker.Mock(return_value=mocker.Mock(
                     text='2024-06-01T12:00:00Z'))))
    result = get_latest_regex_package('cat/pkg-20240601', 'http://example.com', r'(abc123)',
                                      mocker.Mock())
    assert result == ('abc123', '20240601', 'http://example.com')


def test_get_latest_regex_package_commit_hash_parse_error(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.regex.catpkg_catpkgsplit',
                 return_value=('cat', 'pkg', '', '20240601'))
    mock_response = mocker.Mock()
    mock_response.text = 'abc123<invalid>'
    mocker.patch('livecheck.special.regex.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.regex.is_sha', return_value=True)
    mocker.patch('livecheck.special.regex.ET.fromstring', side_effect=ET.ParseError)
    result = get_latest_regex_package('cat/pkg-20240601', 'http://example.com', r'(abc123)',
                                      mocker.Mock())
    assert result == ('', '', '')


def test_get_latest_regex_package_commit_invalid_date(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.regex.catpkg_catpkgsplit',
                 return_value=('cat', 'pkg', '', '202'))
    mock_response = mocker.Mock()
    mock_response.text = '<entry><id>abc123</id><updated>2024-06-01T12:00:00Z</updated></entry>'
    mocker.patch('livecheck.special.regex.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.regex.is_sha', return_value=True)
    mocker.patch('livecheck.special.regex.ET.fromstring',
                 return_value=mocker.Mock(find=mocker.Mock(return_value=mocker.Mock(
                     text='2024-06-01T12:00:00Z'))))
    result = get_latest_regex_package('cat/pkg-20240601', 'http://example.com', r'(abc123)',
                                      mocker.Mock())
    assert result == ('abc123', '', 'http://example.com')


def test_get_latest_regex_package_no_commit_hash_last_version(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.regex.catpkg_catpkgsplit',
                 return_value=('cat', 'pkg', '', '1.0'))
    mock_response = mocker.Mock()
    mock_response.text = 'v1.2.3 v1.2.4'
    mocker.patch('livecheck.special.regex.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.regex.is_sha', return_value=False)
    mocker.patch('re.findall', return_value=['v1.2.3', 'v1.2.4'])
    mocker.patch('livecheck.special.regex.get_last_version', return_value={'version': 'v1.2.4'})
    result = get_latest_regex_package('cat/pkg-1.0', 'http://example.com', r'(v\d+\.\d+\.\d+)',
                                      mocker.Mock())
    assert result == ('v1.2.4', '', '')


def test_get_latest_regex_package_no_commit_hash_no_last_version(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.regex.catpkg_catpkgsplit',
                 return_value=('cat', 'pkg', '', '1.0'))
    mock_response = mocker.Mock()
    mock_response.text = 'v1.2.3 v1.2.4'
    mocker.patch('livecheck.special.regex.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.regex.is_sha', return_value=False)
    mocker.patch('re.findall', return_value=['v1.2.3', 'v1.2.4'])
    mocker.patch('livecheck.special.regex.get_last_version', return_value=None)
    result = get_latest_regex_package('cat/pkg-1.0', 'http://example.com', r'(v\d+\.\d+\.\d+)',
                                      mocker.Mock())
    assert result == ('', '', '')
