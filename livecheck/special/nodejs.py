import subprocess as sp

from loguru import logger

from livecheck.utils import check_program

from .utils import build_compress, remove_url_ebuild, search_ebuild

__all__ = ('check_nodejs_requirements', 'remove_nodejs_url', 'update_nodejs_ebuild')


def remove_nodejs_url(ebuild_content: str) -> str:
    return remove_url_ebuild(ebuild_content, '-node_modules.tar.xz')


def update_nodejs_ebuild(ebuild: str, path: str | None, fetchlist: dict[str, str]) -> None:
    package_path, temp_dir = search_ebuild(ebuild, 'package.json', path)
    if package_path == '':
        return

    try:
        sp.run(('npm', 'install', '--audit false', '--color false', '--progress false',
                '--ignore-scripts'),
               cwd=package_path,
               check=True)
    except sp.CalledProcessError as e:
        logger.error(f"Error running 'npm install': {e}")
        return

    build_compress(temp_dir, package_path, 'node_modules', '-node_modules.tar.xz', fetchlist)


def check_nodejs_requirements() -> bool:
    if not check_program('npm', '--version'):
        logger.error('npm is not installed')
        return False
    return True
