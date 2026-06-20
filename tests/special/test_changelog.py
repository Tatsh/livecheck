from __future__ import annotations

from typing import TYPE_CHECKING, Any

from livecheck.special.changelog import get_latest_changelog_package
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

pytestmark = pytest.mark.asyncio


def make_settings(mocker: MockerFixture) -> Any:
    settings = mocker.Mock()
    settings.request_data = {}
    settings.request_headers = {}
    settings.request_method = {}
    settings.request_params = {}
    return settings


async def test_get_latest_changelog_package_extracts_bracketed_headings(
        mocker: MockerFixture) -> None:
    settings = make_settings(mocker)
    response = mocker.Mock()
    response.text = '# Changelog\n\n## [17.1.0] - 2023-05-29\n\n### Added\n\n## [17.0.0-2]'
    mocker.patch('livecheck.special.changelog.get_content', return_value=response)

    def fake_get_last_version(results: list[dict[str, str]], repo: str, ebuild: str,
                              settings_arg: Any) -> dict[str, str]:
        assert results == [{'tag': '17.1.0'}, {'tag': '17.0.0-2'}]
        assert not repo
        assert ebuild == 'cat/pkg-17.0.0'
        assert settings_arg is settings
        return {'version': '17.1.0'}

    mocker.patch('livecheck.special.changelog.get_last_version', side_effect=fake_get_last_version)
    result = await get_latest_changelog_package('cat/pkg-17.0.0',
                                                'https://example.com/CHANGELOG.md', settings)
    assert result == '17.1.0'


async def test_get_latest_changelog_package_extracts_v_prefixed_headings(
        mocker: MockerFixture) -> None:
    settings = make_settings(mocker)
    response = mocker.Mock()
    response.text = '# Changelog\n\n## v1.1.2\n\n### Added or Changed\n\n## v1.1.1'
    mocker.patch('livecheck.special.changelog.get_content', return_value=response)
    mock_get_last_version = mocker.patch('livecheck.special.changelog.get_last_version',
                                         return_value={'version': '1.1.2'})
    result = await get_latest_changelog_package('cat/pkg-1.1.1', 'https://example.com/CHANGELOG.md',
                                                settings)
    assert result == '1.1.2'
    assert mock_get_last_version.call_args.args[0] == [{'tag': 'v1.1.2'}, {'tag': 'v1.1.1'}]


async def test_get_latest_changelog_package_ignores_date_headings(mocker: MockerFixture) -> None:
    settings = make_settings(mocker)
    response = mocker.Mock()
    response.text = ('# Changelog\n\n## [2024-01-31]\n\n### Added\n\n## 1.2.3\n\n'
                     '### Fixed\n\n## 2023-01-01\n')
    mocker.patch('livecheck.special.changelog.get_content', return_value=response)
    mock_get_last_version = mocker.patch('livecheck.special.changelog.get_last_version',
                                         return_value={'version': '1.2.3'})
    result = await get_latest_changelog_package('cat/pkg-1.0.0', 'https://example.com/CHANGELOG.md',
                                                settings)
    assert result == '1.2.3'
    assert mock_get_last_version.call_args.args[0] == [{'tag': '1.2.3'}]


async def test_get_latest_changelog_package_only_date_headings(mocker: MockerFixture) -> None:
    settings = make_settings(mocker)
    response = mocker.Mock()
    response.text = '# Changelog\n\n## 2024-01-31\n\n### Added\n\n## 2023-01-01\n'
    mocker.patch('livecheck.special.changelog.get_content', return_value=response)
    mock_get_last_version = mocker.patch('livecheck.special.changelog.get_last_version',
                                         return_value={})
    result = await get_latest_changelog_package('cat/pkg-1.0.0', 'https://example.com/CHANGELOG.md',
                                                settings)
    assert not result
    assert mock_get_last_version.call_args.args[0] == []


async def test_get_latest_changelog_package_keeps_date_headings_for_date_version(
        mocker: MockerFixture) -> None:
    settings = make_settings(mocker)
    response = mocker.Mock()
    response.text = '# Changelog\n\n## 2024-01-31\n\n### Added\n\n## 2023-01-01\n'
    mocker.patch('livecheck.special.changelog.get_content', return_value=response)
    mock_get_last_version = mocker.patch('livecheck.special.changelog.get_last_version',
                                         return_value={'version': '2024.01.31'})
    result = await get_latest_changelog_package('cat/pkg-2023.01.01',
                                                'https://example.com/CHANGELOG.md', settings)
    assert result == '2024.01.31'
    assert mock_get_last_version.call_args.args[0] == [{'tag': '2024-01-31'}, {'tag': '2023-01-01'}]


async def test_get_latest_changelog_package_no_content(mocker: MockerFixture) -> None:
    settings = make_settings(mocker)
    mocker.patch('livecheck.special.changelog.get_content', return_value=None)
    result = await get_latest_changelog_package('cat/pkg-1.0.0', 'https://example.com/CHANGELOG.md',
                                                settings)
    assert not result


async def test_get_latest_changelog_package_no_last_version(mocker: MockerFixture) -> None:
    settings = make_settings(mocker)
    response = mocker.Mock()
    response.text = '# Changelog\n\n## Unreleased\n\n### Added\n'
    mocker.patch('livecheck.special.changelog.get_content', return_value=response)
    mock_get_last_version = mocker.patch('livecheck.special.changelog.get_last_version',
                                         return_value={})
    result = await get_latest_changelog_package('cat/pkg-1.0.0', 'https://example.com/CHANGELOG.md',
                                                settings)
    assert not result
    assert mock_get_last_version.call_args.args[0] == []


async def test_get_latest_changelog_package_uses_request_options(mocker: MockerFixture) -> None:
    settings = make_settings(mocker)
    settings.request_data = {'cat/pkg': {'token': 'abc'}}
    settings.request_headers = {'cat/pkg': {'Accept': 'text/markdown'}}
    settings.request_method = {'cat/pkg': 'POST'}
    settings.request_params = {'cat/pkg': {'download': '1'}}
    response = mocker.Mock()
    response.text = '## 2.0.0\n'
    mock_get_content = mocker.patch('livecheck.special.changelog.get_content',
                                    return_value=response)
    mocker.patch('livecheck.special.changelog.get_last_version', return_value={'version': '2.0.0'})
    result = await get_latest_changelog_package('cat/pkg-1.0.0', 'https://example.com/CHANGELOG.md',
                                                settings)
    assert result == '2.0.0'
    mock_get_content.assert_called_once_with('https://example.com/CHANGELOG.md',
                                             data={'token': 'abc'},
                                             headers={'Accept': 'text/markdown'},
                                             method='POST',
                                             params={'download': '1'})
