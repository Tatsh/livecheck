from dataclasses import dataclass
from os.path import basename, dirname
from typing import Callable, Mapping
import glob
import json

from loguru import logger

import livecheck.special_cases as sc

from . import utils

__all__ = ('LivecheckSettings', 'gather_settings')


@dataclass
class LivecheckSettings:
    branches: dict[str, str]
    checksum_livechecks: set[str]
    custom_livechecks: dict[str, tuple[str, str, bool, str]]
    ignored_packages: set[str]
    no_auto_update: set[str]
    sha_sources: dict[str, str]
    transformations: Mapping[str, Callable[[str], str]]


def gather_settings(search_dir: str) -> LivecheckSettings:
    branches = {}
    checksum_livechecks = set()
    custom_livechecks = {}
    ignored_packages = set()
    no_auto_update = set()
    transformations = {}
    sha_sources = {}
    for path in glob.glob(f'{search_dir}/**/livecheck.json', recursive=True):
        logger.debug(f'Opening {path}')
        with open(path) as f:
            dn = dirname(path)
            catpkg = f'{basename(dirname(dn))}/{basename(dn)}'
            settings_parsed = json.load(f)
            if settings_parsed.get('type', None) == 'none':
                ignored_packages.add(catpkg)
            elif settings_parsed.get('type', None) == 'regex':
                custom_livechecks[catpkg] = (settings_parsed['url'], settings_parsed['regex'],
                                             settings_parsed.get('use_vercmp', True),
                                             settings_parsed.get('version', None))
            elif settings_parsed.get('type', None) == 'checksum':
                checksum_livechecks.add(catpkg)
            if settings_parsed.get('branch', None):
                branches[catpkg] = settings_parsed['branch']
            if settings_parsed.get('no_auto_update', None):
                no_auto_update.add(catpkg)
            if settings_parsed.get('transformation_function', None):
                tfs = settings_parsed['transformation_function']
                try:
                    tf: Callable[[str], str] = getattr(sc, tfs)
                except AttributeError:
                    try:
                        tf = getattr(utils, tfs)
                    except AttributeError as e:
                        raise NameError(f'Unknown transformation function: {tfs}') from e
                transformations[catpkg] = tf
            if settings_parsed.get('sha_source', None):
                sha_sources[catpkg] = settings_parsed['sha_source']
    return LivecheckSettings(branches, checksum_livechecks, custom_livechecks, ignored_packages,
                             no_auto_update, sha_sources, transformations)
