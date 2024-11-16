from pathlib import Path
import logging

from xdg.BaseDirectory import save_cache_path

import os
import tarfile
import portage
from ..utils.portage import unpack_ebuild, get_distdir

__all__ = ("get_project_path", "remove_url_ebuild", "search_ebuild", "build_compress")

logger = logging.getLogger(__name__)


def get_project_path(package_name: str) -> Path:
    return Path(save_cache_path(f"livecheck/{package_name}"))


def remove_url_ebuild(ebuild: str, remove: str) -> str:
    lines = ebuild.split('\n')
    filtered_lines = []
    for _, line in enumerate(lines):
        original_line = line
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith('#'):
            filtered_lines.append(original_line)
            continue
        if remove in stripped_line:
            url = stripped_line.strip(' "\'')
            if url.endswith(remove):
                if stripped_line.endswith(('"', "'")):
                    filtered_lines.append(stripped_line[-1])
                continue
        filtered_lines.append(original_line)
    return '\n'.join(filtered_lines)


def search_ebuild(ebuild: str, archive: str, path: str) -> tuple[str, str]:
    temp_dir = unpack_ebuild(ebuild)
    if temp_dir == "":
        logger.warning("Error unpacking the ebuild.")
        return "", ""

    if path:
        # Search first directory in temp_dir
        for root, _, files in os.walk(temp_dir):
            # check if relative path is in the root
            if path in root:
                return root, temp_dir
    else:
        for root, _, files in os.walk(temp_dir):
            if archive in files:
                return root, temp_dir

    logger.error("Error searching the \"{archive}\" inside package.")

    return "", ""


def build_compress(ebuild: str, temp_dir: str, base_dir: str, directory: str,
                   extension: str) -> bool:

    vendor_dir = os.path.join(base_dir, directory)
    if not os.path.exists(vendor_dir):
        logger.warning("The directory vendor was not created.")
        return False

    ebuild_filename = os.path.basename(ebuild)
    cpv = ebuild_filename.replace(".ebuild", "")
    category = os.path.basename(os.path.dirname(os.path.dirname(ebuild)))

    fetchlist = portage.portdb.getFetchMap(f"{category}/{cpv}")
    filename, _ = next(iter(fetchlist.items()))

    if filename.endswith('.tar.gz'):
        archive_ext = '.tar.gz'
    elif filename.endswith('.tgz'):
        archive_ext = '.tgz'
    elif filename.endswith('.tar.xz'):
        archive_ext = '.xz'
    elif filename.endswith('.zip'):
        archive_ext = '.zip'
    else:
        logger.warning("Invalid extension.")
        return False

    base_name = filename[:-len(archive_ext)]
    vendor_archive_name = f"{base_name}{extension}"
    vendor_archive_path = os.path.join(get_distdir(), vendor_archive_name)

    vendor_path = Path(base_dir).resolve()
    base_path = Path(temp_dir).resolve()

    relative_path = os.path.join(vendor_path.relative_to(base_path), directory)

    with tarfile.open(vendor_archive_path, "w:xz") as tar:
        tar.add(vendor_dir, arcname=str(relative_path))

    return True
