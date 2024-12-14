import subprocess as sp
from loguru import logger

from .utils import remove_url_ebuild, search_ebuild, build_compress

__all__ = ("update_gomodule_ebuild", "remove_gomodule_url")


def remove_gomodule_url(ebuild_content: str) -> str:
    return remove_url_ebuild(ebuild_content, '-vendor.tar.xz')


def update_gomodule_ebuild(ebuild: str, path: str | None, fetchlist: dict[str, str]) -> None:
    go_mod_path, temp_dir = search_ebuild(ebuild, 'go.mod', path)
    if go_mod_path == "":
        return

    try:
        sp.run(['go', 'mod', 'vendor'], cwd=go_mod_path, check=True)
    except sp.CalledProcessError as e:
        logger.error(f"Error running 'go mod vendor': {e}")
        return

    build_compress(temp_dir, go_mod_path, 'vendor', "-vendor.tar.xz", fetchlist)
