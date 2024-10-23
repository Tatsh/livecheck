from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
import json
import logging

import livecheck.special.handlers as sc

from . import utils

__all__ = ('LivecheckSettings', 'gather_settings')

logger = logging.getLogger(__name__)


@dataclass
class LivecheckSettings:
    branches: dict[str, str]
    checksum_livechecks: set[str]
    custom_livechecks: dict[str, tuple[str, str, bool, str]]
    dotnet_projects: dict[str, str]
    '''Dictionary of catpkg to project or solution file (base name only).'''
    go_sum_uri: dict[str, str]
    '''
    Dictionary of catpkg to full URI to ``go.sum`` with ``@PV@`` used for where version gets
    placed.
    '''
    ignored_packages: set[str]
    no_auto_update: set[str]
    semver: dict[str, bool]
    '''Disable auto-detection of semantic versioning.'''
    sha_sources: dict[str, str]
    transformations: Mapping[str, Callable[[str], str]]
    yarn_base_packages: dict[str, str]
    yarn_packages: dict[str, set[str]]
    jetbrains_packages: dict[str, bool]
    keep_old: dict[str, bool]


class UnknownTransformationFunction(NameError):
    def __init__(self, tfs: str):
        super().__init__(f'Unknown transformation function: {tfs}')


def gather_settings(search_dir: str) -> LivecheckSettings:
    branches: dict[str, str] = {}
    checksum_livechecks: set[str] = set()
    custom_livechecks: dict[str, tuple[str, str, bool, str]] = {}
    dotnet_projects: dict[str, str] = {}
    golang_packages: dict[str, str] = {}
    ignored_packages: set[str] = set()
    no_auto_update: set[str] = set()
    semver: dict[str, bool] = {}
    sha_sources: dict[str, str] = {}
    transformations: dict[str, Callable[[str], str]] = {}
    yarn_base_packages: dict[str, str] = {}
    yarn_packages: dict[str, set[str]] = {}
    jetbrains_packages: dict[str, bool] = {}
    keep_old: dict[str, bool] = {}
    for path in Path(search_dir).glob('**/livecheck.json'):
        logger.debug('Opening %s', path)
        with path.open() as f:
            dn = path.parent
            catpkg = f'{dn.parent.name}/{dn.name}'
            try:
                settings_parsed = json.load(f)
            except json.JSONDecodeError as e:
                logger.error('Error parsing file %s: %s', path, e)
                continue
            if settings_parsed.get('type') == 'none':
                ignored_packages.add(catpkg)
            elif settings_parsed.get('type') == 'regex':
                custom_livechecks[catpkg] = (settings_parsed['url'], settings_parsed['regex'],
                                             settings_parsed.get('use_vercmp', True),
                                             settings_parsed.get('version', None))
            elif settings_parsed.get('type') == 'checksum':
                checksum_livechecks.add(catpkg)
            if settings_parsed.get('branch'):
                branches[catpkg] = settings_parsed['branch']
            if 'no_auto_update' in settings_parsed:
                no_auto_update.add(catpkg)
            if settings_parsed.get('transformation_function', None):
                tfs = settings_parsed['transformation_function']
                try:
                    tf: Callable[[str], str] = getattr(sc, tfs)
                except AttributeError:
                    try:
                        tf = getattr(utils, tfs)
                    except AttributeError as e:
                        raise UnknownTransformationFunction(tfs) from e
                transformations[catpkg] = tf
            if settings_parsed.get('sha_source'):
                sha_sources[catpkg] = settings_parsed['sha_source']
            if settings_parsed.get('yarn_base_package'):
                yarn_base_packages[catpkg] = settings_parsed['yarn_base_package']
                if settings_parsed.get('yarn_packages'):
                    yarn_packages[catpkg] = set(settings_parsed['yarn_packages'])
            if settings_parsed.get('go_sum_uri'):
                golang_packages[catpkg] = settings_parsed['go_sum_uri']
            if settings_parsed.get('dotnet_project'):
                dotnet_projects[catpkg] = settings_parsed['dotnet_project']
            if 'semver' in settings_parsed:
                semver[catpkg] = settings_parsed['semver']
            if 'jetbrains' in settings_parsed:
                jetbrains_packages[catpkg] = settings_parsed['jetbrains']
            if 'keep_old' in settings_parsed:
                keep_old[catpkg] = settings_parsed['keep_old']
    return LivecheckSettings(branches, checksum_livechecks, custom_livechecks, dotnet_projects,
                             golang_packages, ignored_packages, no_auto_update, semver, sha_sources,
                             transformations, yarn_base_packages, yarn_packages, jetbrains_packages,
                             keep_old)
