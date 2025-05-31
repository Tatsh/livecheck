from __future__ import annotations

from typing import IO, TYPE_CHECKING, Any

from livecheck.special.dotnet import (
    NoNugetsEnding,
    NoNugetsFound,
    check_dotnet_requirements,
    dotnet_restore,
    update_dotnet_ebuild,
)
from typing_extensions import Self
import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.logging import LogCaptureFixture
    from pytest_mock import MockerFixture


def _get_fake_temp_dir(path: str) -> Any:
    """Return a fake temporary directory path."""
    class _FakeTempDir:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.path = path

        def __enter__(self) -> str:
            return self.path

        def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
            pass

        def open(self, mode: str, encoding: str | None = None) -> IO[Any]:
            return open(self.path, mode, encoding=encoding)  # noqa: PTH123

    return _FakeTempDir


def test_dotnet_restore_yields_expected_packages(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch('livecheck.special.dotnet.tempfile.TemporaryDirectory',
                 _get_fake_temp_dir(str(tmp_path)))
    mock_run = mocker.patch('livecheck.special.dotnet.sp.run')
    find_output = (f'{tmp_path}/Newtonsoft.Json@13.0.1\n'
                   f'{tmp_path}/SomeOther.Package@2.1.0\n'
                   f'{tmp_path}/microsoft.aspnetcore.app.host@9.0.0\n'
                   f'{tmp_path}/runtime.win@8.0.0\n'
                   f'{tmp_path}/NotAPackage\n')

    def run_side_effect(args: list[str], **kwargs: Any) -> Any:
        if args[0] == 'dotnet':
            return mocker.Mock()
        if args[0] == 'find':
            return mocker.Mock(stdout=find_output)
        raise ValueError

    mock_run.side_effect = run_side_effect

    project_file = tmp_path / 'proj.csproj'
    project_file.write_text('<Project></Project>')
    results = list(dotnet_restore(project_file))
    assert results == ['Newtonsoft.Json@13.0.1', 'SomeOther.Package@2.1.0']


def test_dotnet_restore_filters_correctly(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch('livecheck.special.dotnet.tempfile.TemporaryDirectory',
                 _get_fake_temp_dir(str(tmp_path)))
    mock_run = mocker.patch('livecheck.special.dotnet.sp.run')
    find_output = (f'{tmp_path}/microsoft.netcore.app.ref@9.0.0\n'
                   f'{tmp_path}/runtime.win@8.0.0\n'
                   f'{tmp_path}/Valid.Package@1.2.3\n')

    def run_side_effect(args: Any, **kwargs: Any) -> Any:
        if args[0] == 'dotnet':
            return mocker.Mock()
        if args[0] == 'find':
            return mocker.Mock(stdout=find_output)
        return None

    mock_run.side_effect = run_side_effect
    project_file = tmp_path / 'proj.csproj'
    project_file.write_text('<Project></Project>')
    results = list(dotnet_restore(project_file))
    assert results == ['Valid.Package@1.2.3']


def test_dotnet_restore_handles_no_packages(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_run = mocker.patch('subprocess.run')
    find_output = ''

    def run_side_effect(args: Any, **kwargs: Any) -> Any:
        if args[0] == 'dotnet':
            return mocker.Mock()
        if args[0] == 'find':
            return mocker.Mock(stdout=find_output)
        return None

    mock_run.side_effect = run_side_effect
    project_file = tmp_path / 'proj.csproj'
    project_file.write_text('<Project></Project>')
    results = list(dotnet_restore(project_file))
    assert results == []


def test_dotnet_restore_raises_on_dotnet_failure(mocker: MockerFixture, tmp_path: Path) -> None:
    # Simulate dotnet restore failing
    def run_side_effect(args: Any, **kwargs: Any) -> Any:
        if args[0] == 'dotnet':
            msg = 'dotnet restore failed'
            raise RuntimeError(msg)
        if args[0] == 'find':
            return mocker.Mock(stdout='')
        return None

    mocker.patch('subprocess.run', side_effect=run_side_effect)
    project_file = tmp_path / 'proj.csproj'
    project_file.write_text('<Project></Project>')
    with pytest.raises(RuntimeError):
        list(dotnet_restore(project_file))


class _DummyTempFile:
    def __init__(self, path: str) -> None:
        self.path = path

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass

    def open(self, mode: str, encoding: str | None = None) -> IO[Any]:
        return open(self.path, mode, encoding=encoding)  # noqa: PTH123


def test_update_dotnet_ebuild_updates_nugets_correctly(mocker: MockerFixture,
                                                       tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    project_name = 'proj.csproj'
    project_path = tmp_path / project_name
    project_path.write_text('<Project></Project>')
    ebuild_content = [
        'EAPI=8\n', 'NUGETS="\n', '    Old.Package@1.0.0"\n', 'SOME_OTHER_VAR="foo"\n'
    ]
    ebuild_path.write_text(''.join(ebuild_content))
    mocker.patch('livecheck.special.dotnet.search_ebuild', return_value=(str(tmp_path), None))
    mocker.patch('livecheck.special.dotnet.dotnet_restore',
                 return_value=iter(['New.Package@2.0.0', 'Another.Package@3.1.4']))
    update_dotnet_ebuild(str(ebuild_path), project_name)
    # Check that the ebuild file was updated with new NUGETS
    lines = ebuild_path.read_text().splitlines()
    assert any('NUGETS="' in line for line in lines)
    assert any('New.Package@2.0.0' in line for line in lines)
    assert any('Another.Package@3.1.4' in line for line in lines)
    assert not any('Old.Package@1.0.0' in line for line in lines)


def test_update_dotnet_ebuild_raises_no_nugets_found(mocker: MockerFixture, tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    ebuild_path.write_text('EAPI=8\nSOME_OTHER_VAR="foo"\n')
    mocker.patch('livecheck.special.dotnet.search_ebuild', return_value=(str(tmp_path), None))
    mocker.patch('livecheck.special.dotnet.dotnet_restore', return_value=iter([]))
    mocker.patch('livecheck.special.dotnet.EbuildTempFile', _DummyTempFile)
    proj_csproj = tmp_path / 'proj.csproj'
    proj_csproj.write_text('<Project></Project>')
    with pytest.raises(NoNugetsFound):
        update_dotnet_ebuild(str(ebuild_path), proj_csproj)


def test_update_dotnet_ebuild_raises_runtime_error(mocker: MockerFixture, tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    ebuild_path.write_text('EAPI=8\nNUGETS="\nfoo\nbar\nNUGETS="\n')
    mocker.patch('livecheck.special.dotnet.search_ebuild', return_value=(str(tmp_path), None))
    mocker.patch('livecheck.special.dotnet.dotnet_restore', return_value=iter([]))
    proj_csproj = tmp_path / 'proj.csproj'
    proj_csproj.write_text('<Project></Project>')
    with pytest.raises(RuntimeError):
        update_dotnet_ebuild(str(ebuild_path), proj_csproj)


def test_update_dotnet_ebuild_raises_no_nugets_ending(mocker: MockerFixture,
                                                      tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    ebuild_path.write_text('EAPI=8\nNUGETS="\nfoo\nbar\n')
    mocker.patch('livecheck.special.dotnet.search_ebuild', return_value=(str(tmp_path), None))
    mocker.patch('livecheck.special.dotnet.dotnet_restore', return_value=iter([]))
    proj_csproj = tmp_path / 'proj.csproj'
    proj_csproj.write_text('<Project></Project>')
    with pytest.raises(NoNugetsEnding):
        update_dotnet_ebuild(str(ebuild_path), proj_csproj)


def test_update_dotnet_ebuild_returns_if_no_dotnet_path(mocker: MockerFixture,
                                                        tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    ebuild_path.write_text('EAPI=8\nNUGETS="\n    Old.Package@1.0.0"\n')
    mocker.patch('livecheck.special.dotnet.search_ebuild', return_value=(None, None))
    update_dotnet_ebuild(str(ebuild_path), 'proj.csproj')
    assert 'Old.Package@1.0.0' in ebuild_path.read_text()


def test_check_dotnet_requirements_returns_true_for_valid_version(mocker: MockerFixture) -> None:
    # Mock check_program to return True (dotnet >= 10.0.0)
    mocker.patch('livecheck.special.dotnet.check_program', return_value=True)
    assert check_dotnet_requirements() is True


def test_check_dotnet_requirements_returns_false_for_invalid_version(mocker: MockerFixture) -> None:
    # Mock check_program to return False (dotnet < 10.0.0 or not installed)
    mocker.patch('livecheck.special.dotnet.check_program', return_value=False)
    assert check_dotnet_requirements() is False


def test_check_dotnet_requirements_logs_error_on_failure(mocker: MockerFixture,
                                                         caplog: LogCaptureFixture) -> None:
    # Mock check_program to return False
    mocker.patch('livecheck.special.dotnet.check_program', return_value=False)
    with caplog.at_level('ERROR'):
        result = check_dotnet_requirements()
    assert result is False
    assert any(
        'dotnet is not installed or version is less than 9.0.0.' in m for m in caplog.messages)
