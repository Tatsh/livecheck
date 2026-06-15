""".NET functions."""
from __future__ import annotations

from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING
import asyncio
import logging
import re
import tempfile

from anyio import Path as AnyioPath
from livecheck.utils import check_program

from .utils import (
    EbuildTempFile,
    build_compress,
    dist_archive_already_uploaded,
    remove_url_ebuild,
    search_ebuild,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from livecheck.dist_github import DistGitHubSettings

__all__ = ('check_dotnet_requirements', 'remove_dotnet_url', 'update_dotnet_archive_ebuild',
           'update_dotnet_ebuild')

log = logging.getLogger(__name__)


async def dotnet_restore(project_or_solution: str | Path) -> AsyncIterator[str]:
    """
    Restore NuGet packages for a project and yield cache-relative package paths.

    Parameters
    ----------
    project_or_solution : str | Path
        Project or solution file passed to ``dotnet restore``.

    Yields
    ------
    str
        Package directory names suitable for ``NUGETS`` entries.

    Raises
    ------
    FileNotFoundError
        If ``dotnet`` or ``find`` is not available on ``PATH``.
    """
    dotnet_exe = which('dotnet')
    find_exe = which('find')
    if dotnet_exe is None or find_exe is None:
        msg = 'dotnet and find must be available on PATH'
        raise FileNotFoundError(msg)
    with tempfile.TemporaryDirectory(prefix='livecheck-dotnet-', ignore_cleanup_errors=True) as td:
        proc = await asyncio.create_subprocess_exec(dotnet_exe, 'restore', str(project_or_solution),
                                                    '--force', '-v', 'm', '--packages', td)
        await proc.wait()
        if proc.returncode != 0:
            return
        find_proc = await asyncio.create_subprocess_exec(find_exe,
                                                         td,
                                                         '-maxdepth',
                                                         '1',
                                                         '-type',
                                                         'd',
                                                         '-exec',
                                                         find_exe,
                                                         '{}',
                                                         '-maxdepth',
                                                         '1',
                                                         '-type',
                                                         'd',
                                                         ';',
                                                         stdout=asyncio.subprocess.PIPE)
        stdout, _ = await find_proc.communicate()
        packages = [
            x for x in (re.sub(f'^{re.escape(td)}/', '', line).replace('/', '@')
                        for line in stdout.decode().splitlines())
            if (not re.match(r'^microsoft\.(?:asp)?netcore\.app\.(?:host|ref|runtime)', x)
                and not re.match(r'^runtime\.win', x) and re.search(r'@[0-9]', x))
        ]
    for package in packages:
        yield package


class NoNugetsEnding(RuntimeError):
    """Raised when the end of the ``NUGETS`` variable cannot be determined."""
    def __init__(self) -> None:
        super().__init__('Unable to determine of end of NUGETS')


class NoNugetsFound(RuntimeError):
    """Raised when no ``NUGETS`` variable is found in the ebuild."""
    def __init__(self) -> None:
        super().__init__('No NUGETS variable found in ebuild')


async def update_dotnet_ebuild(ebuild: str, project_or_solution: str | Path) -> None:
    """
    Update a .NET ebuild with the latest ``NUGETS``.

    Raises
    ------
    NoNugetsEnding
        If the end of the ``NUGETS`` variable cannot be determined.
    NoNugetsFound
        If no ``NUGETS`` variable is found in the ebuild.
    RuntimeError
        If the ``NUGETS`` variable is malformed or if multiple candidates are found.
    """
    project_or_solution = Path(project_or_solution)
    dotnet_path, _ = await search_ebuild(ebuild, project_or_solution.name, '')
    if not dotnet_path:
        return

    project = Path(dotnet_path) / project_or_solution
    new_nugets_lines = sorted([x async for x in dotnet_restore(project.resolve(strict=True))])

    last_line_no = len(new_nugets_lines)
    in_nugets = False
    skip_lines = None
    nugets_starting_line = None

    async with EbuildTempFile(ebuild) as temp_file:
        ebuild_text = await AnyioPath(ebuild).read_text(encoding='utf-8')
        lines = ebuild_text.splitlines(keepends=True)

        for line_no, line in enumerate(lines, start=1):
            if line.startswith('NUGETS="'):
                nugets_starting_line = line_no
                if in_nugets:
                    raise RuntimeError
                in_nugets = True
            elif in_nugets:
                if line.endswith('"\n'):
                    in_nugets = False
                    skip_lines = line_no
                    break
        if not nugets_starting_line:
            raise NoNugetsFound
        if not skip_lines:
            raise NoNugetsEnding

        in_nugets = False
        out: list[str] = []
        for line in lines:
            if line.startswith('NUGETS="'):
                out.append('NUGETS="')
                in_nugets = True
            elif in_nugets:
                for new_line_no, pkg in enumerate(new_nugets_lines, start=1):
                    match new_line_no:
                        case 1:
                            out.append(f'{pkg}\n')
                        case _:
                            out.append(f'\t{pkg}"\n' if last_line_no ==
                                       new_line_no else f'\t{pkg}\n')
                in_nugets = False
            else:
                out.append(line)
        await AnyioPath(temp_file).write_text(''.join(out), encoding='utf-8')


def remove_dotnet_url(ebuild_content: str) -> str:
    """
    Remove ``-nuget.tar.xz`` line from ebuild.

    Parameters
    ----------
    ebuild_content : str
        Full ebuild file text.

    Returns
    -------
    str
        Ebuild text with the NuGet archive URL line removed.
    """
    return remove_url_ebuild(ebuild_content, '-nuget.tar.xz')


async def update_dotnet_archive_ebuild(ebuild: str,
                                       project_or_solution: str | Path,
                                       fetchlist: Mapping[str, tuple[str, ...]],
                                       *,
                                       dist_settings: DistGitHubSettings | None = None) -> None:
    """
    Build (and optionally upload) a NuGet packages vendor archive for a .NET ebuild.

    The archive is created from a project-local ``packages`` directory populated by
    ``dotnet restore --packages``.

    Parameters
    ----------
    ebuild : str
        Path to the ebuild file.
    project_or_solution : str | pathlib.Path
        Project or solution file relative to the unpacked source tree.
    fetchlist : Mapping[str, tuple[str, ...]]
        Fetch map used when compressing vendor output.
    dist_settings : DistGitHubSettings | None
        Optional GitHub release destination for the produced archive.
    """
    if await dist_archive_already_uploaded('-nuget.tar.xz', fetchlist, dist_settings):
        log.info('NuGet archive already uploaded; skipping `dotnet restore`.')
        return
    project_or_solution = Path(project_or_solution)
    dotnet_path, temp_dir = await search_ebuild(ebuild, project_or_solution.name, '')
    if not dotnet_path:
        return
    project = Path(dotnet_path) / project_or_solution
    dotnet_exe = which('dotnet')
    if dotnet_exe is None:
        log.error('dotnet executable not found in PATH.')
        return
    packages_dir = Path(dotnet_path) / 'packages'
    try:
        proc = await asyncio.create_subprocess_exec(dotnet_exe, 'restore',
                                                    str(project.resolve(strict=True)), '--force',
                                                    '-v', 'm', '--packages', str(packages_dir))
        returncode = await proc.wait()
        if returncode != 0:
            log.error("Error running 'dotnet restore'.")
            return
    except OSError:
        log.exception("Error running 'dotnet restore'.")
        return
    await build_compress(temp_dir,
                         dotnet_path,
                         'packages',
                         '-nuget.tar.xz',
                         fetchlist,
                         dist_settings=dist_settings)


def check_dotnet_requirements() -> bool:
    """
    Check if dotnet is installed and its version is at least 9.0.0.

    Returns
    -------
    bool
        ``True`` if ``dotnet`` meets the version requirement, otherwise ``False``.
    """
    if not check_program('dotnet', ['--version'], '10.0.0'):
        log.error('dotnet is not installed or version is less than 9.0.0.')
        return False
    return True
