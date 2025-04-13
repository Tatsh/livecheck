import subprocess as sp

from loguru import logger

from livecheck.utils import check_program

from .utils import build_compress, remove_url_ebuild, search_ebuild

__all__ = ('check_gomodule_requirements', 'remove_gomodule_url', 'update_gomodule_ebuild')


def remove_gomodule_url(ebuild_content: str) -> str:
    return remove_url_ebuild(ebuild_content, '-vendor.tar.xz')


def update_gomodule_ebuild(ebuild: str, path: str | None, fetchlist: dict[str, str]) -> None:
    go_mod_path, temp_dir = search_ebuild(ebuild, 'go.mod', path)
    if go_mod_path == '':
        return

    try:
        sp.run(['go', 'mod', 'vendor'], cwd=go_mod_path, check=True)
    except sp.CalledProcessError as e:
        logger.error(f"Error running 'go mod vendor': {e}")
        return

    build_compress(temp_dir, go_mod_path, 'vendor', '-vendor.tar.xz', fetchlist)


def check_gomodule_requirements() -> bool:
    if not check_program('go', 'version'):
        logger.error('go is not installed')
        return False
    return True
