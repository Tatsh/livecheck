from pathlib import Path
import re
import tempfile

import requests

__all__ = ('update_go_ebuild',)


def update_go_ebuild(ebuild: str | Path, pkg: str, version: str, go_sum_uri_template: str) -> None:
    ebuild = Path(ebuild)
    if '@PV@' not in go_sum_uri_template:
        raise ValueError('URI template missing @PV@')
    uri = go_sum_uri_template.replace('@PV@', version)
    r = requests.get(uri)
    r.raise_for_status()
    new_ego_sum_lines = []
    for line in (re.sub(r' h1\:.*$', '', x) for x in r.text.splitlines()):
        new_ego_sum_lines.append(f'"{line}"')
    in_ego_sum = False
    tf = tempfile.NamedTemporaryFile(mode='w',
                                     prefix=ebuild.stem,
                                     suffix=ebuild.suffix,
                                     delete=False,
                                     dir=ebuild.parent)
    wrote_new_packages = False
    with ebuild.open('r') as f:
        for line in f.readlines():
            if line.startswith('EGO_SUM=('):
                tf.write(line)
                if in_ego_sum:
                    raise RuntimeError
                in_ego_sum = True
            elif in_ego_sum:
                if line.strip() == ')':
                    in_ego_sum = False
                    tf.write(line)
                elif not wrote_new_packages:
                    for pkg in new_ego_sum_lines:
                        tf.write(f'\t{pkg}\n')
                    wrote_new_packages = True
            else:
                tf.write(line)
    ebuild.unlink()
    Path(tf.name).rename(ebuild).chmod(0o0644)
