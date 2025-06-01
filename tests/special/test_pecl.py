from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special.pecl import (
    get_latest_pecl_metadata,
    get_latest_pecl_package,
    get_latest_pecl_package2,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_latest_pecl_package_removes_prefix_and_calls_helper(mocker: MockerFixture) -> None:
    ebuild = 'dev-php/pecl-foo-1.0.0'
    settings = mocker.Mock()
    mocker.patch('livecheck.special.pecl.catpkg_catpkgsplit',
                 return_value=('dev-php', None, 'pecl-foo', None))
    helper = mocker.patch('livecheck.special.pecl.get_latest_pecl_package2', return_value='1.2.3')
    result = get_latest_pecl_package(ebuild, settings)
    helper.assert_called_once_with('foo', ebuild, settings)
    assert result == '1.2.3'


def test_get_latest_pecl_package_no_prefix(mocker: MockerFixture) -> None:
    ebuild = 'dev-php/foo-1.0.0'
    settings = mocker.Mock()
    mocker.patch('livecheck.special.pecl.catpkg_catpkgsplit',
                 return_value=('dev-php', None, 'foo', None))
    helper = mocker.patch('livecheck.special.pecl.get_latest_pecl_package2', return_value='2.0.0')

    result = get_latest_pecl_package(ebuild, settings)
    helper.assert_called_once_with('foo', ebuild, settings)
    assert result == '2.0.0'


def test_get_latest_pecl_package2_returns_latest_stable(mocker: MockerFixture) -> None:
    ebuild = 'dev-php/foo-1.0.0'
    settings = mocker.Mock()
    settings.is_devel.return_value = False
    mocker.patch('livecheck.special.pecl.catpkg_catpkgsplit',
                 return_value=('dev-php', None, 'foo', None))
    xml = """
    <a xmlns="http://pear.php.net/dtd/rest.allreleases">
      <r><v>1.0.0</v><s>stable</s></r>
      <r><v>1.1.0</v><s>beta</s></r>
      <r><v>2.0.0</v><s>stable</s></r>
    </a>
    """
    mock_get_content = mocker.patch('livecheck.special.pecl.get_content',
                                    return_value=mocker.Mock(text=xml))
    mock_get_last_version = mocker.patch('livecheck.special.pecl.get_last_version',
                                         return_value={'version': '2.0.0'})

    result = get_latest_pecl_package2('foo', ebuild, settings)

    assert result == '2.0.0'
    mock_get_content.assert_called_once()
    mock_get_last_version.assert_called_once()


def test_get_latest_pecl_package2_returns_empty_on_no_content(mocker: MockerFixture) -> None:
    ebuild = 'dev-php/foo-1.0.0'
    settings = mocker.Mock()
    mocker.patch('livecheck.special.pecl.catpkg_catpkgsplit',
                 return_value=('dev-php', None, 'foo', None))
    mocker.patch('livecheck.special.pecl.get_content', return_value=None)

    result = get_latest_pecl_package2('foo', ebuild, settings)
    assert not result


def test_get_latest_pecl_package2_returns_empty_on_no_last_version(mocker: MockerFixture) -> None:
    ebuild = 'dev-php/foo-1.0.0'
    settings = mocker.Mock()
    mocker.patch('livecheck.special.pecl.catpkg_catpkgsplit',
                 return_value=('dev-php', None, 'foo', None))
    xml = """
    <a xmlns="http://pear.php.net/dtd/rest.allreleases">
      <r><v>1.0.0</v><s>stable</s></r>
    </a>
    """
    mocker.patch('livecheck.special.pecl.get_content', return_value=mocker.Mock(text=xml))
    mocker.patch('livecheck.special.pecl.get_last_version', return_value=None)

    get_latest_pecl_package2('foo', ebuild, settings)


def test_get_latest_pecl_package2_filters_only_stable_when_not_devel(mocker: MockerFixture) -> None:
    ebuild = 'dev-php/foo-1.0.0'
    settings = mocker.Mock()
    settings.is_devel.return_value = False
    mocker.patch('livecheck.special.pecl.catpkg_catpkgsplit',
                 return_value=('dev-php', None, 'foo', None))
    xml = """
    <a xmlns="http://pear.php.net/dtd/rest.allreleases">
        <r><v>1.0.0</v><s>stable</s></r>
        <r><v>1.1.0</v><s>beta</s></r>
        <r><v>2.0.0</v><s>stable</s></r>
        <r><v>3.0.0</v><s>alpha</s></r>
    </a>
    """
    mocker.patch('livecheck.special.pecl.get_content', return_value=mocker.Mock(text=xml))
    mock_get_last_version = mocker.patch('livecheck.special.pecl.get_last_version',
                                         return_value={'version': '2.0.0'})

    result = get_latest_pecl_package2('foo', ebuild, settings)

    assert result == '2.0.0'
    mock_get_last_version.assert_called_once()
    # Only stable versions should be considered
    args, _kwargs = mock_get_last_version.call_args
    tags = args[0]
    assert all(tag['tag'] in {'1.0.0', '2.0.0'} for tag in tags)


def test_get_latest_pecl_package2_includes_all_when_devel(mocker: MockerFixture) -> None:
    ebuild = 'dev-php/foo-1.0.0'
    settings = mocker.Mock()
    settings.is_devel.return_value = True
    mocker.patch('livecheck.special.pecl.catpkg_catpkgsplit',
                 return_value=('dev-php', None, 'foo', None))
    xml = """
    <a xmlns="http://pear.php.net/dtd/rest.allreleases">
        <r><v>1.0.0</v><s>stable</s></r>
        <r><v>1.1.0</v><s>beta</s></r>
        <r><v>2.0.0</v><s>stable</s></r>
        <r><v>3.0.0</v><s>alpha</s></r>
    </a>
    """
    mocker.patch('livecheck.special.pecl.get_content', return_value=mocker.Mock(text=xml))
    mock_get_last_version = mocker.patch('livecheck.special.pecl.get_last_version',
                                         return_value={'version': '3.0.0'})

    result = get_latest_pecl_package2('foo', ebuild, settings)

    assert result == '3.0.0'
    mock_get_last_version.assert_called_once()
    args, _kwargs = mock_get_last_version.call_args
    tags = args[0]
    # All versions should be included
    assert {tag['tag'] for tag in tags} == {'1.0.0', '1.1.0', '2.0.0', '3.0.0'}


def test_get_latest_pecl_package2_returns_empty_if_no_releases(mocker: MockerFixture) -> None:
    ebuild = 'dev-php/foo-1.0.0'
    settings = mocker.Mock()
    settings.is_devel.return_value = False
    mocker.patch('livecheck.special.pecl.catpkg_catpkgsplit',
                 return_value=('dev-php', None, 'foo', None))
    xml = """
    <a xmlns="http://pear.php.net/dtd/rest.allreleases">
    </a>
    """
    mocker.patch('livecheck.special.pecl.get_content', return_value=mocker.Mock(text=xml))
    mock_get_last_version = mocker.patch('livecheck.special.pecl.get_last_version',
                                         return_value=None)

    result = get_latest_pecl_package2('foo', ebuild, settings)
    assert not result
    mock_get_last_version.assert_called_once()


def test_get_latest_pecl_metadata_calls_helper_with_correct_args(mocker: MockerFixture) -> None:
    remote = 'foo'
    ebuild = 'dev-php/foo-1.0.0'
    settings = mocker.Mock()
    mock_helper = mocker.patch('livecheck.special.pecl.get_latest_pecl_package2',
                               return_value='9.9.9')
    result = get_latest_pecl_metadata(remote, ebuild, settings)
    mock_helper.assert_called_once_with(remote, ebuild, settings)
    assert result == '9.9.9'


def test_get_latest_pecl_metadata_returns_empty_when_helper_returns_empty(
        mocker: MockerFixture) -> None:
    remote = 'foo'
    ebuild = 'dev-php/foo-1.0.0'
    settings = mocker.Mock()
    mocker.patch('livecheck.special.pecl.get_latest_pecl_package2', return_value='')
    result = get_latest_pecl_metadata(remote, ebuild, settings)
    assert not result


def test_get_latest_pecl_metadata_passes_through_exceptions(mocker: MockerFixture) -> None:
    remote = 'foo'
    ebuild = 'dev-php/foo-1.0.0'
    settings = mocker.Mock()
    mocker.patch('livecheck.special.pecl.get_latest_pecl_package2', side_effect=ValueError('fail'))
    with pytest.raises(ValueError, match='fail'):
        get_latest_pecl_metadata(remote, ebuild, settings)
