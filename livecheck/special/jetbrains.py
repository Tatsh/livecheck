import tempfile
import tarfile
import io
from pathlib import Path

import requests
from loguru import logger
from .utils import search_ebuild

__all__ = ("get_latest_jetbrains_package", "update_jetbrains_ebuild")


def get_latest_jetbrains_package(product_code: str, development: bool = False) -> str:
    api_url = "https://data.services.jetbrains.com/products"
    product_name = {
        'phpstorm': 'PhpStorm',
        'pycharm-community': 'PyCharm Community Edition',
        'pycharm-professional': 'PyCharm Professional Edition',
        'idea-community': 'IntelliJ IDEA Community Edition',
        'clion': 'CLion',
        'goland': 'GoLand',
    }

    product_code = product_name.get(product_code, product_code)

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        products_info = response.json()

        for product in products_info:
            if product['name'] == product_code:
                for release in product['releases']:
                    if (release['type'] == 'eap' or release['type'] == 'rc') and not development:
                        continue
                    if 'linux' in release['downloads']:
                        latest_version = release['version']
                        return str(latest_version)

        logger.debug(f"Version information not found for {product_code}.")

    except requests.exceptions.HTTPError as e:
        logger.debug(f"Error accessing the URL: {e}")

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
