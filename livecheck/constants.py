"""Constants."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .utils import prefix_v

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = ('PACKAGE_MANAGERS', 'RSS_NS', 'SUBMODULES', 'TAG_NAME_FUNCTIONS')

PACKAGE_MANAGERS = frozenset({'npm', 'pnpm', 'yarn'})

RSS_NS = {'': 'http://www.w3.org/2005/Atom'}
"""
Namespace for RSS feeds.

:meta hide-value:
"""
SUBMODULES: Mapping[str, set[str | tuple[str, str] | tuple[str, str, str]]] = {
    'app-misc/tasksh': {'src/libshared'},
    'app-pda/tsschecker': {'external/jssy'},
    'games-emulation/citra': {
        'externals/dynarmic', 'externals/fmt', 'externals/lodepng/lodepng', 'externals/sirit',
        'externals/soundtouch', 'externals/xbyak'
    },
    'games-emulation/play': {
        'deps/CodeGen', 'deps/Dependencies', 'deps/Framework', 'deps/Nuanceur', 'deps/libchdr'
    },
    'games-emulation/rpcs3': {
        '3rdparty/asmjit/asmjit', '3rdparty/hidapi/hidapi', '3rdparty/yaml-cpp/yaml-cpp',
        '3rdparty/SoundTouch/soundtouch', '3rdparty/llvm/llvm'
    },
    'games-emulation/sudachi': {
        'externals/SDL', 'externals/cpp-httplib', 'externals/cpp-jwt', 'externals/dynarmic',
        'externals/ffmpeg/ffmpeg', 'externals/mbedtls', 'externals/simpleini', 'externals/sirit',
        'externals/xbyak'
    },
    'games-emulation/vita3k': {
        'external/LibAtrac9', 'external/SPIRV-Cross', 'external/VulkanMemoryAllocator-Hpp',
        'external/better-enums', 'external/concurrentqueue', 'external/dirent', 'external/dlmalloc',
        'external/glslang', 'external/googletest', 'external/imgui', 'external/imgui_club',
        'external/libadrenotools', 'external/libfat16', 'external/printf', 'external/psvpfstools',
        'external/substitute', 'external/vita-toolchain', ('external/dynarmic', '_DYNARMIC_SHA'),
        ('Vulkan-Headers', 'VULKANMEMORYALLOCATOR_HPP_VULKAN_HEADERS_SHA',
         'external/VulkanMemoryAllocator-Hpp'),
        ('VulkanMemoryAllocator', 'VULKANMEMORYALLOCATOR_HPP_VULKANMEMORYALLOCATOR_SHA',
         'external/VulkanMemoryAllocator-Hpp'),
        ('lib/linkernsbypass', 'LIBADRENOTOOLS_LIB_LINKERNSBYPASS_SHA', 'external/libadrenotools'),
        ('libb64', 'PSVPFSTOOLS_LIBB64_SHA', 'external/psvpfstools'),
        ('libzrif', 'PSVPFSTOOLS_LIBZRIF_SHA', 'external/psvpfstools'),
        ('psvpfsparser', 'PSVPFSTOOLS_PSVPFSPARSER_SHA', 'external/psvpfstools'),
        ('zlib', 'PSVPFSTOOLS_ZLIB_SHA', 'external/psvpfstools'),
        ('psp2rela', 'VITA_TOOLCHAIN_PSP2RELA_SHA', 'external/vita-toolchain')
    },
    'games-emulation/yuzu': {
        'externals/SDL', 'externals/cpp-jwt', 'externals/dynarmic', 'externals/mbedtls',
        'externals/sirit', ('externals/cpp-httplib', 'HTTPLIB_SHA')
    },
    'media-sound/sony-headphones-client': {'Client/imgui'}
}
"""
Currently, submodule handling is hard-coded for specific packages.

:meta hide-value:
"""
TAG_NAME_FUNCTIONS: Mapping[str, Callable[[str], str]] = {
    'app-misc/tasksh': prefix_v,
    'games-emulation/rpcs3': prefix_v,
    'games-emulation/xemu': prefix_v,
    'games-emulation/yuzu': lambda x: f'mainline-{x.replace(".", "-")}',
    'media-sound/sony-headphones-client': prefix_v
}
"""
Functions to prefix tag names for specific packages.

:meta hide-value:
"""
