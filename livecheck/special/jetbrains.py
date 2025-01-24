import tempfile
from pathlib import Path

from loguru import logger
from .utils import search_ebuild

from ..settings import LivecheckSettings
from ..utils.portage import get_last_version, catpkg_catpkgsplit
from ..utils import get_content

__all__ = ("get_latest_jetbrains_package", "update_jetbrains_ebuild")


def get_latest_jetbrains_package(ebuild: str, development: bool, restrict_version: str,
                                 settings: LivecheckSettings) -> str:
    api_url = "https://data.services.jetbrains.com/products"
    product_name = {
        'phpstorm': 'PhpStorm',
        'pycharm-community': 'PyCharm Community Edition',
        'pycharm-professional': 'PyCharm Professional Edition',
        'idea-community': 'IntelliJ IDEA Community Edition',
        'clion': 'CLion',
        'goland': 'GoLand',
    }

    _, _, product_code, _ = catpkg_catpkgsplit(ebuild)

    product_code = product_name.get(product_code, product_code)
    results = []

    if not (response := get_content(api_url)):
        return ''

    for product in response.json():
        if product['name'] == product_code:
            for release in product['releases']:
                if (release['type'] == 'eap' or release['type'] == 'rc') and not development:
                    continue
                if 'linux' in release.get('downloads', ''):
                    results.append({"tag": release['version']})

    result = get_last_version(results, '', ebuild, development, restrict_version, settings)
    if result:
        return result['tag']

    return ''


def update_jetbrains_ebuild(ebuild: str | Path) -> None:
    package_path, _ = search_ebuild(str(ebuild), 'product-info.json')
    version = package_path.split('/')[-1]
    if not version:
        logger.warning('No version found in the tar.gz file.')
        return

    version = version.split('-', 1)[-1]

    ebuild = Path(ebuild)
    tf = tempfile.NamedTemporaryFile(mode='w',
                                     prefix=ebuild.stem,
                                     suffix=ebuild.suffix,
                                     delete=False,
                                     dir=ebuild.parent)
    with ebuild.open('r') as f:
        for line in f.readlines():
            if line.startswith('MY_PV='):
                logger.debug('Found MY_PV= line.')
                tf.write(f'MY_PV="{version}"\n')
            else:
                tf.write(line)
    ebuild.unlink()
    Path(tf.name).rename(ebuild).chmod(0o0644)
