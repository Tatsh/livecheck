from collections.abc import Iterator
from functools import cmp_to_key
from pathlib import Path
from urllib.parse import urlparse
import re
import shutil
import subprocess as sp
import tempfile

import requests

from ..utils import unique_justseen
from ..utils.portage import P, catpkg_catpkgsplit, get_first_src_uri, sort_by_v

__all__ = ('update_dotnet_ebuild',)


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


def update_dotnet_ebuild(ebuild: str | Path, project_or_solution: str | Path, cp: str) -> None:
    ebuild = Path(ebuild)
    project_or_solution = Path(project_or_solution)
    with tempfile.TemporaryDirectory(prefix='livecheck-dotnet-', ignore_cleanup_errors=True) as td:
        sp.run(('ebuild', str(ebuild), 'manifest'), check=True)
        matches = list(
            unique_justseen(sorted(set(P.xmatch('match-all', cp)), key=cmp_to_key(sort_by_v)),
                            key=lambda a: catpkg_catpkgsplit(a)[0]))
        if not matches:
            raise NoMatch(cp)
        new_src_uri = get_first_src_uri(matches[0])
        archive_out_name = Path(urlparse(new_src_uri).path).name
        archive_out_path = Path(td) / archive_out_name
        with archive_out_path.open('w+b') as f, requests.get(new_src_uri, stream=True) as r:
            for data in r.iter_content(chunk_size=512):
                f.write(data)
        r.raise_for_status()
        shutil.unpack_archive(str(archive_out_path), td)
        run = sp.run(('find', td, '-maxdepth', '2', '-name', project_or_solution.name),
                     check=True,
                     stdout=sp.PIPE,
                     text=True)
        lines = run.stdout.splitlines()
        if not lines:
            raise ProjectFileNotFound(project_or_solution)
        if len(lines) > 1:
            raise TooManyProjects(project_or_solution)
        new_nugets_lines = sorted(dotnet_restore(Path(lines[0]).resolve(strict=True)))
    last_line_no = len(new_nugets_lines)
    in_nugets = False
    tf = tempfile.NamedTemporaryFile(mode='w',
                                     prefix=ebuild.stem,
                                     suffix=ebuild.suffix,
                                     delete=False,
                                     dir=ebuild.parent)
    skip_lines = None
    nugets_starting_line = None
    with ebuild.open('r') as f:
        for line_no, line in enumerate(f.readlines(), start=1):
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
        f.seek(0)
        for line_no, line in enumerate(f.readlines(), start=1):
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
                            tf.write(f'\t{pkg}"\n' if last_line_no == new_line_no else f'\t{pkg}\n')
                in_nugets = False
            elif line_no > skip_lines or line_no < nugets_starting_line:
                tf.write(line)
    ebuild.unlink()
    Path(tf.name).rename(ebuild).chmod(0o0644)
