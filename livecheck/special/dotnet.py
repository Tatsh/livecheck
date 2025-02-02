from collections.abc import Iterator
from pathlib import Path
import re
import subprocess as sp
import tempfile

from loguru import logger
from .utils import EbuildTempFile, search_ebuild
from ..utils import check_program

__all__ = ('update_dotnet_ebuild', 'check_dotnet_requirements')


def dotnet_restore(project_or_solution: str | Path) -> Iterator[str]:
    with tempfile.TemporaryDirectory(prefix='livecheck-dotnet-', ignore_cleanup_errors=True) as td:
        sp.run(
            ('dotnet', 'restore', str(project_or_solution), '--force', '-v', 'm', '--packages', td),
            check=True)
        yield from (x for x in (re.sub(f'^{re.escape(td)}/', '', line).replace('/', '@')
                                for line in sp.run(('find', td, '-maxdepth', '1', '-type', 'd',
                                                    '-exec', 'find', '{}', '-maxdepth', '1',
                                                    '-type', 'd', ';'),
                                                   check=True,
                                                   text=True,
                                                   stdout=sp.PIPE).stdout.splitlines())
                    if not re.match(r'^microsoft\.(?:asp)?netcore\.app\.(?:host|ref|runtime)', x)
                    and not re.match(r'^runtime\.win', x) and re.search(r'@[0-9]', x))


class NoMatch(RuntimeError):
    def __init__(self, cp: str) -> None:
        super().__init__(f'No match for {cp}')


class ProjectFileNotFound(FileNotFoundError):
    def __init__(self, project_or_solution: str | Path) -> None:
        super().__init__(f'Project file {project_or_solution} was not found.')


class TooManyProjects(RuntimeError):
    def __init__(self, project_or_solution: str | Path) -> None:
        super().__init__(f'Found multiple candidates of {project_or_solution}.')


class NoNugetsEnding(RuntimeError):
    def __init__(self) -> None:
        super().__init__('Unable to determine of end of NUGETS')


class NoNugetsFound(RuntimeError):
    def __init__(self) -> None:
        super().__init__('No NUGETS variable found in ebuild')


def update_dotnet_ebuild(ebuild: str, project_or_solution: str | Path) -> None:
    project_or_solution = Path(project_or_solution)
    dotnet_path, _ = search_ebuild(ebuild, project_or_solution.name, '')
    if dotnet_path == "":
        return

    project = Path(dotnet_path) / project_or_solution
    new_nugets_lines = sorted(dotnet_restore(project.resolve(strict=True)))

    last_line_no = len(new_nugets_lines)
    in_nugets = False
    skip_lines = None
    nugets_starting_line = None

    with EbuildTempFile(ebuild) as temp_file:
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
            if not skip_lines:
                raise NoNugetsEnding
            if not nugets_starting_line:
                raise NoNugetsFound

            for line_no, line in enumerate(lines, start=1):
                if line.startswith('NUGETS="'):
                    tf.write('NUGETS="')
                    if in_nugets:
                        raise RuntimeError
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
                elif line_no > skip_lines or line_no < nugets_starting_line:
                    tf.write(line)


def check_dotnet_requirements() -> bool:
    if not check_program('dotnet', '--version', '10.0.0'):
        logger.error('dotnet is not installed or version is less than 9.0.0')
        return False
    return True
