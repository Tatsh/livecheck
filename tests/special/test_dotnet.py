from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

from livecheck.special.dotnet import (
    NoNugetsEnding,
    NoNugetsFound,
    check_dotnet_requirements,
    dotnet_restore,
    remove_dotnet_url,
    update_dotnet_archive_ebuild,
    update_dotnet_ebuild,
)
import pytest

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture
    from pytest_mock import MockerFixture


def _get_fake_temp_dir(path: str) -> Any:
    """Return a fake temporary directory context manager."""
    class _FakeTempDir:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.path = path

        def __enter__(self) -> str:
            return self.path

        def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
            pass

    return _FakeTempDir


@pytest.mark.asyncio
async def test_dotnet_restore_yields_expected_packages(mocker: MockerFixture,
                                                       tmp_path: Path) -> None:
    mocker.patch('livecheck.special.dotnet.tempfile.TemporaryDirectory',
                 _get_fake_temp_dir(str(tmp_path)))
    mocker.patch('livecheck.special.dotnet.which', side_effect=lambda n: f'/bin/{n}')

    find_output = (f'{tmp_path}/Newtonsoft.Json@13.0.1\n'
                   f'{tmp_path}/SomeOther.Package@2.1.0\n'
                   f'{tmp_path}/microsoft.aspnetcore.app.host@9.0.0\n'
                   f'{tmp_path}/runtime.win@8.0.0\n'
                   f'{tmp_path}/NotAPackage\n')

    def create_subprocess_side_effect(*args: Any, **kwargs: Any) -> Any:
        mock_proc = mocker.MagicMock()
        if args[0] == '/bin/dotnet':
            mock_proc.wait = AsyncMock(return_value=0)
            mock_proc.returncode = 0
            return mock_proc
        if args[0] == '/bin/find':
            mock_proc.communicate = AsyncMock(return_value=(find_output.encode(), b''))
            mock_proc.returncode = 0
            return mock_proc
        raise ValueError

    mocker.patch('livecheck.special.dotnet.asyncio.create_subprocess_exec',
                 side_effect=create_subprocess_side_effect)

    project_file = tmp_path / 'proj.csproj'
    project_file.write_text('<Project></Project>')
    results = [x async for x in dotnet_restore(project_file)]
    assert results == ['Newtonsoft.Json@13.0.1', 'SomeOther.Package@2.1.0']


@pytest.mark.asyncio
async def test_dotnet_restore_filters_correctly(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch('livecheck.special.dotnet.tempfile.TemporaryDirectory',
                 _get_fake_temp_dir(str(tmp_path)))
    mocker.patch('livecheck.special.dotnet.which', side_effect=lambda n: f'/bin/{n}')

    find_output = (f'{tmp_path}/microsoft.netcore.app.ref@9.0.0\n'
                   f'{tmp_path}/runtime.win@8.0.0\n'
                   f'{tmp_path}/Valid.Package@1.2.3\n')

    def create_subprocess_side_effect(*args: Any, **kwargs: Any) -> Any:
        mock_proc = mocker.MagicMock()
        if args[0] == '/bin/dotnet':
            mock_proc.wait = AsyncMock(return_value=0)
            mock_proc.returncode = 0
            return mock_proc
        if args[0] == '/bin/find':
            mock_proc.communicate = AsyncMock(return_value=(find_output.encode(), b''))
            mock_proc.returncode = 0
            return mock_proc
        return None

    mocker.patch('livecheck.special.dotnet.asyncio.create_subprocess_exec',
                 side_effect=create_subprocess_side_effect)

    project_file = tmp_path / 'proj.csproj'
    project_file.write_text('<Project></Project>')
    results = [x async for x in dotnet_restore(project_file)]
    assert results == ['Valid.Package@1.2.3']


@pytest.mark.asyncio
async def test_dotnet_restore_handles_no_packages(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch('livecheck.special.dotnet.tempfile.TemporaryDirectory',
                 _get_fake_temp_dir(str(tmp_path)))
    mocker.patch('livecheck.special.dotnet.which', side_effect=lambda n: f'/bin/{n}')

    def create_subprocess_side_effect(*args: Any, **kwargs: Any) -> Any:
        mock_proc = mocker.MagicMock()
        if args[0] == '/bin/dotnet':
            mock_proc.wait = AsyncMock(return_value=0)
            mock_proc.returncode = 0
            return mock_proc
        if args[0] == '/bin/find':
            mock_proc.communicate = AsyncMock(return_value=(b'', b''))
            mock_proc.returncode = 0
            return mock_proc
        return None

    mocker.patch('livecheck.special.dotnet.asyncio.create_subprocess_exec',
                 side_effect=create_subprocess_side_effect)

    project_file = tmp_path / 'proj.csproj'
    project_file.write_text('<Project></Project>')
    results = [x async for x in dotnet_restore(project_file)]
    assert results == []


@pytest.mark.asyncio
async def test_dotnet_restore_returns_on_nonzero_returncode(mocker: MockerFixture,
                                                            tmp_path: Path) -> None:
    mocker.patch('livecheck.special.dotnet.tempfile.TemporaryDirectory',
                 _get_fake_temp_dir(str(tmp_path)))
    mocker.patch('livecheck.special.dotnet.which', side_effect=lambda n: f'/bin/{n}')

    def create_subprocess_side_effect(*args: Any, **kwargs: Any) -> Any:
        mock_proc = mocker.MagicMock()
        if args[0] == '/bin/dotnet':
            mock_proc.wait = AsyncMock(return_value=1)
            mock_proc.returncode = 1
            return mock_proc
        return mocker.MagicMock()

    mocker.patch('livecheck.special.dotnet.asyncio.create_subprocess_exec',
                 side_effect=create_subprocess_side_effect)
    project_file = tmp_path / 'proj.csproj'
    project_file.write_text('<Project></Project>')
    results = [x async for x in dotnet_restore(project_file)]
    assert results == []


@pytest.mark.asyncio
async def test_dotnet_restore_raises_on_dotnet_failure(mocker: MockerFixture,
                                                       tmp_path: Path) -> None:
    mocker.patch('livecheck.special.dotnet.tempfile.TemporaryDirectory',
                 _get_fake_temp_dir(str(tmp_path)))
    mocker.patch('livecheck.special.dotnet.which', side_effect=lambda n: f'/bin/{n}')

    def create_subprocess_side_effect(*args: Any, **kwargs: Any) -> Any:
        if args[0] == '/bin/dotnet':
            msg = 'dotnet restore failed'
            raise RuntimeError(msg)
        mock_proc = mocker.MagicMock()
        if args[0] == '/bin/find':
            mock_proc.communicate = AsyncMock(return_value=(b'', b''))
            return mock_proc
        return None

    mocker.patch('livecheck.special.dotnet.asyncio.create_subprocess_exec',
                 side_effect=create_subprocess_side_effect)

    project_file = tmp_path / 'proj.csproj'
    project_file.write_text('<Project></Project>')
    with pytest.raises(RuntimeError):
        _ = [x async for x in dotnet_restore(project_file)]


@pytest.mark.asyncio
async def test_dotnet_restore_raises_when_dotnet_or_find_missing(mocker: MockerFixture,
                                                                 tmp_path: Path) -> None:
    mocker.patch('livecheck.special.dotnet.which', return_value=None)
    project_file = tmp_path / 'proj.csproj'
    project_file.write_text('<Project></Project>')
    with pytest.raises(FileNotFoundError, match='dotnet and find must be available on PATH'):
        _ = [x async for x in dotnet_restore(project_file)]


class _FakeEbuildTempFile:
    """Fake EbuildTempFile for testing update_dotnet_ebuild."""
    def __init__(self, ebuild: str) -> None:
        self._ebuild = Path(ebuild)
        self._temp: Path | None = None

    async def __aenter__(self) -> Path:
        import tempfile as tf
        self._temp = Path(
            tf.NamedTemporaryFile(  # ruff:ignore[open-file-with-context-handler]
                mode='w',
                prefix=self._ebuild.stem,
                suffix=self._ebuild.suffix,
                delete=False,
                dir=str(self._ebuild.parent),
                encoding='utf-8').name)
        return self._temp

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if exc_type is None and self._temp and self._temp.exists() and self._temp.stat().st_size:
            self._ebuild.unlink(missing_ok=True)
            self._temp.rename(self._ebuild)
            self._ebuild.chmod(0o0644)
        if self._temp and self._temp.exists():
            self._temp.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_update_dotnet_ebuild_updates_nugets_correctly(mocker: MockerFixture,
                                                             tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    project_name = 'proj.csproj'
    project_path = tmp_path / project_name
    project_path.write_text('<Project></Project>')
    ebuild_content = [
        'EAPI=8\n', 'NUGETS="\n', '    Old.Package@1.0.0"\n', 'SOME_OTHER_VAR="foo"\n'
    ]
    ebuild_path.write_text(''.join(ebuild_content))
    mocker.patch('livecheck.special.dotnet.search_ebuild',
                 new_callable=AsyncMock,
                 return_value=(str(tmp_path), None))

    async def _mock_dotnet_restore(_: Any) -> Any:  # ruff:ignore[unused-async]
        for pkg in ('New.Package@2.0.0', 'Another.Package@3.1.4'):
            yield pkg

    mocker.patch('livecheck.special.dotnet.dotnet_restore', side_effect=_mock_dotnet_restore)
    mocker.patch('livecheck.special.dotnet.EbuildTempFile', _FakeEbuildTempFile)
    await update_dotnet_ebuild(str(ebuild_path), project_name)
    lines = ebuild_path.read_text().splitlines()
    assert any('NUGETS="' in line for line in lines)
    assert any('New.Package@2.0.0' in line for line in lines)
    assert any('Another.Package@3.1.4' in line for line in lines)
    assert not any('Old.Package@1.0.0' in line for line in lines)


@pytest.mark.asyncio
async def test_update_dotnet_ebuild_raises_no_nugets_found(mocker: MockerFixture,
                                                           tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    ebuild_path.write_text('EAPI=8\nSOME_OTHER_VAR="foo"\n')
    mocker.patch('livecheck.special.dotnet.search_ebuild',
                 new_callable=AsyncMock,
                 return_value=(str(tmp_path), None))

    async def _mock_dotnet_restore(_: Any) -> Any:  # ruff:ignore[unused-async]
        return
        yield

    mocker.patch('livecheck.special.dotnet.dotnet_restore', side_effect=_mock_dotnet_restore)
    mocker.patch('livecheck.special.dotnet.EbuildTempFile', _FakeEbuildTempFile)
    proj_csproj = tmp_path / 'proj.csproj'
    proj_csproj.write_text('<Project></Project>')
    with pytest.raises(NoNugetsFound):
        await update_dotnet_ebuild(str(ebuild_path), proj_csproj)


@pytest.mark.asyncio
async def test_update_dotnet_ebuild_raises_runtime_error(mocker: MockerFixture,
                                                         tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    ebuild_path.write_text('EAPI=8\nNUGETS="\nfoo\nbar\nNUGETS="\n')
    mocker.patch('livecheck.special.dotnet.search_ebuild',
                 new_callable=AsyncMock,
                 return_value=(str(tmp_path), None))

    async def _mock_dotnet_restore(_: Any) -> Any:  # ruff:ignore[unused-async]
        return
        yield

    mocker.patch('livecheck.special.dotnet.dotnet_restore', side_effect=_mock_dotnet_restore)
    mocker.patch('livecheck.special.dotnet.EbuildTempFile', _FakeEbuildTempFile)
    proj_csproj = tmp_path / 'proj.csproj'
    proj_csproj.write_text('<Project></Project>')
    with pytest.raises(RuntimeError):
        await update_dotnet_ebuild(str(ebuild_path), proj_csproj)


@pytest.mark.asyncio
async def test_update_dotnet_ebuild_raises_no_nugets_ending(mocker: MockerFixture,
                                                            tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    ebuild_path.write_text('EAPI=8\nNUGETS="\nfoo\nbar\n')
    mocker.patch('livecheck.special.dotnet.search_ebuild',
                 new_callable=AsyncMock,
                 return_value=(str(tmp_path), None))

    async def _mock_dotnet_restore(_: Any) -> Any:  # ruff:ignore[unused-async]
        return
        yield

    mocker.patch('livecheck.special.dotnet.dotnet_restore', side_effect=_mock_dotnet_restore)
    mocker.patch('livecheck.special.dotnet.EbuildTempFile', _FakeEbuildTempFile)
    proj_csproj = tmp_path / 'proj.csproj'
    proj_csproj.write_text('<Project></Project>')
    with pytest.raises(NoNugetsEnding):
        await update_dotnet_ebuild(str(ebuild_path), proj_csproj)


@pytest.mark.asyncio
async def test_update_dotnet_ebuild_returns_if_no_dotnet_path(mocker: MockerFixture,
                                                              tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    ebuild_path.write_text('EAPI=8\nNUGETS="\n    Old.Package@1.0.0"\n')
    mocker.patch('livecheck.special.dotnet.search_ebuild',
                 new_callable=AsyncMock,
                 return_value=(None, None))
    await update_dotnet_ebuild(str(ebuild_path), 'proj.csproj')
    assert 'Old.Package@1.0.0' in ebuild_path.read_text()


def test_check_dotnet_requirements_returns_true_for_valid_version(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.dotnet.check_program', return_value=True)
    assert check_dotnet_requirements() is True


def test_check_dotnet_requirements_returns_false_for_invalid_version(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.dotnet.check_program', return_value=False)
    assert check_dotnet_requirements() is False


def test_check_dotnet_requirements_logs_error_on_failure(mocker: MockerFixture,
                                                         caplog: LogCaptureFixture) -> None:
    mocker.patch('livecheck.special.dotnet.check_program', return_value=False)
    with caplog.at_level('ERROR'):
        result = check_dotnet_requirements()
    assert result is False
    assert any(
        'dotnet is not installed or version is less than 9.0.0.' in m for m in caplog.messages)


def test_remove_dotnet_url_strips_nuget_archive_line() -> None:
    content = ('SRC_URI="https://github.com/Tatsh/foo/archive/1.0.tar.gz\n'
               '\thttps://github.com/Tatsh/foo/releases/download/dist/foo-1.0-nuget.tar.xz"\n')
    assert 'nuget.tar.xz' not in remove_dotnet_url(content)


def test_remove_dotnet_url_preserves_unrelated_content() -> None:
    content = 'SRC_URI="https://example.com/foo-1.0.tar.gz"\n'
    assert remove_dotnet_url(content) == content


@pytest.mark.asyncio
async def test_update_dotnet_archive_ebuild_happy_path(mocker: MockerFixture,
                                                       tmp_path: Path) -> None:
    project = tmp_path / 'proj.csproj'
    project.write_text('<Project></Project>')
    mocker.patch('livecheck.special.dotnet.dist_archive_already_uploaded',
                 new_callable=AsyncMock,
                 return_value=False)
    mocker.patch('livecheck.special.dotnet.search_ebuild',
                 new_callable=AsyncMock,
                 return_value=(str(tmp_path), str(tmp_path)))
    mocker.patch('livecheck.special.dotnet.which', return_value='/bin/dotnet')

    proc = mocker.MagicMock()
    proc.wait = AsyncMock(return_value=0)
    mocker.patch('livecheck.special.dotnet.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=proc)
    build = mocker.patch('livecheck.special.dotnet.build_compress',
                         new_callable=AsyncMock,
                         return_value=True)
    await update_dotnet_archive_ebuild(str(tmp_path / 'pkg-1.ebuild'),
                                       'proj.csproj', {'foo-1.tar.gz': ()},
                                       dist_settings=None)
    build.assert_awaited_once()
    call = build.await_args
    assert call is not None
    assert call.args[3] == '-nuget.tar.xz'
    assert call.kwargs == {'dist_settings': None}


@pytest.mark.asyncio
async def test_update_dotnet_archive_ebuild_skips_when_uploaded(mocker: MockerFixture,
                                                                tmp_path: Path) -> None:
    mocker.patch('livecheck.special.dotnet.dist_archive_already_uploaded',
                 new_callable=AsyncMock,
                 return_value=True)
    search = mocker.patch('livecheck.special.dotnet.search_ebuild', new_callable=AsyncMock)
    await update_dotnet_archive_ebuild(str(tmp_path / 'pkg-1.ebuild'), 'proj.csproj',
                                       {'foo-1.tar.gz': ()})
    search.assert_not_called()


@pytest.mark.asyncio
async def test_update_dotnet_archive_ebuild_returns_when_no_dotnet(mocker: MockerFixture,
                                                                   tmp_path: Path) -> None:
    mocker.patch('livecheck.special.dotnet.dist_archive_already_uploaded',
                 new_callable=AsyncMock,
                 return_value=False)
    mocker.patch('livecheck.special.dotnet.search_ebuild',
                 new_callable=AsyncMock,
                 return_value=(str(tmp_path), str(tmp_path)))
    project = tmp_path / 'proj.csproj'
    project.write_text('<Project></Project>')
    mocker.patch('livecheck.special.dotnet.which', return_value=None)
    build = mocker.patch('livecheck.special.dotnet.build_compress', new_callable=AsyncMock)
    await update_dotnet_archive_ebuild(str(tmp_path / 'pkg-1.ebuild'), 'proj.csproj',
                                       {'foo-1.tar.gz': ()})
    build.assert_not_called()


@pytest.mark.asyncio
async def test_update_dotnet_archive_ebuild_returns_when_restore_fails(
        mocker: MockerFixture, tmp_path: Path) -> None:
    project = tmp_path / 'proj.csproj'
    project.write_text('<Project></Project>')
    mocker.patch('livecheck.special.dotnet.dist_archive_already_uploaded',
                 new_callable=AsyncMock,
                 return_value=False)
    mocker.patch('livecheck.special.dotnet.search_ebuild',
                 new_callable=AsyncMock,
                 return_value=(str(tmp_path), str(tmp_path)))
    mocker.patch('livecheck.special.dotnet.which', return_value='/bin/dotnet')
    proc = mocker.MagicMock()
    proc.wait = AsyncMock(return_value=1)
    mocker.patch('livecheck.special.dotnet.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=proc)
    build = mocker.patch('livecheck.special.dotnet.build_compress', new_callable=AsyncMock)
    await update_dotnet_archive_ebuild(str(tmp_path / 'pkg-1.ebuild'), 'proj.csproj',
                                       {'foo-1.tar.gz': ()})
    build.assert_not_called()


@pytest.mark.asyncio
async def test_update_dotnet_archive_ebuild_returns_on_oserror(mocker: MockerFixture,
                                                               tmp_path: Path) -> None:
    project = tmp_path / 'proj.csproj'
    project.write_text('<Project></Project>')
    mocker.patch('livecheck.special.dotnet.dist_archive_already_uploaded',
                 new_callable=AsyncMock,
                 return_value=False)
    mocker.patch('livecheck.special.dotnet.search_ebuild',
                 new_callable=AsyncMock,
                 return_value=(str(tmp_path), str(tmp_path)))
    mocker.patch('livecheck.special.dotnet.which', return_value='/bin/dotnet')
    mocker.patch('livecheck.special.dotnet.asyncio.create_subprocess_exec',
                 side_effect=OSError('boom'))
    build = mocker.patch('livecheck.special.dotnet.build_compress', new_callable=AsyncMock)
    await update_dotnet_archive_ebuild(str(tmp_path / 'pkg-1.ebuild'), 'proj.csproj',
                                       {'foo-1.tar.gz': ()})
    build.assert_not_called()


@pytest.mark.asyncio
async def test_update_dotnet_archive_ebuild_returns_when_search_empty(mocker: MockerFixture,
                                                                      tmp_path: Path) -> None:
    mocker.patch('livecheck.special.dotnet.dist_archive_already_uploaded',
                 new_callable=AsyncMock,
                 return_value=False)
    mocker.patch('livecheck.special.dotnet.search_ebuild',
                 new_callable=AsyncMock,
                 return_value=('', ''))
    build = mocker.patch('livecheck.special.dotnet.build_compress', new_callable=AsyncMock)
    await update_dotnet_archive_ebuild(str(tmp_path / 'pkg-1.ebuild'), 'proj.csproj',
                                       {'foo-1.tar.gz': ()})
    build.assert_not_called()
