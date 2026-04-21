""".NET functions."""
from __future__ import annotations

from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING
import asyncio
import logging
import re
import tempfile

from livecheck.utils import check_program

from .utils import EbuildTempFile, search_ebuild

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

__all__ = ('check_dotnet_requirements', 'update_dotnet_ebuild')

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
        for x in (re.sub(f'^{re.escape(td)}/', '', line).replace('/', '@')
                  for line in stdout.decode().splitlines()):
            if (not re.match(r'^microsoft\.(?:asp)?netcore\.app\.(?:host|ref|runtime)', x)
                    and not re.match(r'^runtime\.win', x) and re.search(r'@[0-9]', x)):
                yield x


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
        with temp_file.open('w', encoding='utf-8') as tf:
            with Path(ebuild).open('r', encoding='utf-8') as f:
                lines = f.readlines()

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
            for line in lines:
                if line.startswith('NUGETS="'):
                    tf.write('NUGETS="')
                    in_nugets = True
                elif in_nugets:
                    for new_line_no, pkg in enumerate(new_nugets_lines, start=1):
                        match new_line_no:
                            case 1:
                                tf.write(f'{pkg}\n')
                            case _:
                                tf.write(f'\t{pkg}"\n' if last_line_no ==
                                         new_line_no else f'\t{pkg}\n')
                    in_nugets = False
                else:
                    tf.write(line)


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
