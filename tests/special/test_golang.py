from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from livecheck.special.golang import InvalidGoSumURITemplate, update_go_ebuild
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def ebuild_file(tmp_path: Path) -> str:
    ebuild = tmp_path / 'test.ebuild'
    ebuild.write_text('EGO_SUM=(\n'
                      '\t"old-pkg v1.0.0"\n'
                      ')\n'
                      'SHA="abcdef123456"\n',
                      encoding='utf-8')
    return str(ebuild)


def test_update_go_ebuild_success(mocker: MockerFixture, ebuild_file: str) -> None:
    # Mock get_content to return a fake response with .text attribute
    mock_response = mocker.Mock()
    mock_response.text = 'pkg1 v1.2.3 h1:abc\npkg2 v2.3.4 h1:def'
    mocker.patch('livecheck.special.golang.get_content', return_value=mock_response)
    update_go_ebuild(ebuild_file, '1.2.3', 'https://example/@PV@/@SHA@/gosum')
    content = Path(ebuild_file).read_text(encoding='utf-8')
    assert 'EGO_SUM=(' in content
    assert '"pkg1 v1.2.3"' in content
    assert '"pkg2 v2.3.4"' in content
    assert 'SHA="abcdef123456"' in content


def test_update_go_ebuild_invalid_template(mocker: MockerFixture, ebuild_file: str) -> None:
    with pytest.raises(InvalidGoSumURITemplate):
        update_go_ebuild(ebuild_file, '1.2.3', 'https://example/gosum')


def test_update_go_ebuild_no_sha(mocker: MockerFixture, tmp_path: Path) -> None:
    ebuild = tmp_path / 'test2.ebuild'
    ebuild.write_text('EGO_SUM=(\n'
                      '\t"old-pkg v1.0.0"\n'
                      ')\n', encoding='utf-8')
    mock_response = mocker.Mock()
    mock_response.text = 'pkg1 v1.2.3 h1:abc'
    mocker.patch('livecheck.special.golang.get_content', return_value=mock_response)
    update_go_ebuild(str(ebuild), '1.2.3', 'https://example/@PV@/@SHA@/gosum')
    content = ebuild.read_text(encoding='utf-8')
    assert '"pkg1 v1.2.3"' in content


def test_update_go_ebuild_no_content(mocker: MockerFixture, ebuild_file: str) -> None:
    mocker.patch('livecheck.special.golang.get_content', return_value=None)
    update_go_ebuild(ebuild_file, '1.2.3', 'https://example/@PV@/@SHA@/gosum')
    # Should not change the file
    content = Path(ebuild_file).read_text(encoding='utf-8')
    assert '"old-pkg v1.0.0"' in content


def test_update_go_ebuild_ego_sum_not_found(mocker: MockerFixture, tmp_path: Path) -> None:
    ebuild = tmp_path / 'test3.ebuild'
    ebuild.write_text('SOMETHING_ELSE=(\n'
                      '\t"not ego sum"\n'
                      ')\n', encoding='utf-8')
    mock_response = mocker.Mock()
    mock_response.text = 'pkg1 v1.2.3 h1:abc'
    mocker.patch('livecheck.special.golang.get_content', return_value=mock_response)
    update_go_ebuild(str(ebuild), '1.2.3', 'https://example/@PV@/@SHA@/gosum')
    content = ebuild.read_text(encoding='utf-8')
    # Should not add new EGO_SUM if not present
    assert 'pkg1 v1.2.3' not in content
