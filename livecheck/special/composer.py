import subprocess as sp

from loguru import logger

from ..utils import check_program
from .utils import build_compress, remove_url_ebuild, search_ebuild

__all__ = ("update_composer_ebuild", "remove_composer_url", "check_composer_requirements")


def remove_composer_url(ebuild_content: str) -> str:
    return remove_url_ebuild(ebuild_content, '-vendor.tar.xz')


def update_composer_ebuild(ebuild: str, path: str | None, fetchlist: dict[str, str]) -> None:
    composer_path, temp_dir = search_ebuild(ebuild, 'composer.json', path)
    if composer_path == "":
        return

    try:
        sp.run(['composer', '--no-interaction', '--no-scripts', 'install'],
               cwd=composer_path,
               check=True)
    except sp.CalledProcessError as e:
        logger.error(f"Error running 'composer': {e}")
        return

    build_compress(temp_dir, composer_path, 'vendor', "-vendor.tar.xz", fetchlist)


def check_composer_requirements() -> bool:
    if not check_program('composer', '--version'):
        logger.error('composer is not installed')
        return False
    return True
