from __future__ import annotations

from typing import TYPE_CHECKING, Any

from livecheck.special.package import extract_project, get_latest_package, is_package
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

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


def make_mock_response(versions: Any) -> Any:
    class MockResponse:
        def json(self) -> Any:  # noqa: PLR6301
            return {'versions': versions}

    return MockResponse()


def test_get_latest_package_success(mocker: MockerFixture) -> None:
    src_uri = 'https://registry.npmjs.org/package-name'
    ebuild = 'package-name-1.0.0.ebuild'
    settings = mocker.Mock()
    mocker.patch('livecheck.special.package.extract_project',
                 return_value=('registry.npmjs.org', 'package-name'))
    mock_get_content = mocker.patch('livecheck.special.package.get_content',
                                    return_value=make_mock_response(['1.0.0', '2.0.0']))
    mock_get_last_version = mocker.patch('livecheck.special.package.get_last_version',
                                         return_value={'version': '2.0.0'})
    result = get_latest_package(src_uri, ebuild, settings)
    assert result == '2.0.0'
    mock_get_content.assert_called_once()
    mock_get_last_version.assert_called_once()


def test_get_latest_package_no_versions(mocker: MockerFixture) -> None:
    src_uri = 'https://registry.npmjs.org/package-name'
    ebuild = 'package-name-1.0.0.ebuild'
    settings = mocker.Mock()
    mocker.patch('livecheck.special.package.extract_project',
                 return_value=('registry.npmjs.org', 'package-name'))
    mocker.patch('livecheck.special.package.get_content', return_value=make_mock_response([]))
    mocker.patch('livecheck.special.package.get_last_version', return_value=None)
    result = get_latest_package(src_uri, ebuild, settings)
    assert not result


def test_get_latest_package_invalid_url(mocker: MockerFixture) -> None:
    src_uri = 'https://invalid.url'
    ebuild = 'package-name-1.0.0.ebuild'
    settings = mocker.Mock()
    mocker.patch('livecheck.special.package.extract_project', return_value=('', ''))
    result = get_latest_package(src_uri, ebuild, settings)
    assert not result


def test_get_latest_package_get_content_returns_none(mocker: MockerFixture) -> None:
    src_uri = 'https://registry.npmjs.org/package-name'
    ebuild = 'package-name-1.0.0.ebuild'
    settings = mocker.Mock()
    mocker.patch('livecheck.special.package.extract_project',
                 return_value=('registry.npmjs.org', 'package-name'))
    mocker.patch('livecheck.special.package.get_content', return_value=None)
    result = get_latest_package(src_uri, ebuild, settings)
    assert not result
