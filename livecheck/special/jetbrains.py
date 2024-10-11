import requests
import tempfile
import tarfile
import io

from pathlib import Path
from loguru import logger

__all__ = ("def get_latest_jetbrains_package", "update_jetbrains_ebuild")


# TODO: Support for EAP versions
def get_latest_jetbrains_package(product_code: str, developer: bool = False) -> tuple[str, str]:
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
                    if release['type'] == 'eap' and not developer:
                        continue
                    if 'linux' in release['downloads']:
                        latest_version = release['version']
                        download_url = release['downloads']['linux']['link']
                        return latest_version, download_url

        logger.debug(f"Version information not found for {product_code}.")

    except requests.exceptions.HTTPError as e:
        logger.debug(f"Error accessing the URL: {e}")

    return '', ''


def get_first_directory_in_tar_gz(url: str) -> str | None:
    response = requests.get(url)
    response.raise_for_status()

    fileobj = io.BytesIO(response.content)
    with tarfile.open(fileobj=fileobj, mode='r:gz') as tar:
        for member in tar.getmembers():
            if member.isdir():
                return member.name.rstrip('/')
    return None


def update_jetbrains_ebuild(ebuild: str | Path, url: str) -> None:
    version = get_first_directory_in_tar_gz(url)

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
