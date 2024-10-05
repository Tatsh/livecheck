import requests

from loguru import logger

__all__ = ("def get_latest_jetbrains_package",)


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
