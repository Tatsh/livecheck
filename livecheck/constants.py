from collections.abc import Callable, Mapping
from typing import Final

from .utils import prefix_v

__all__ = ('RSS_NS', 'SUBMODULES', 'TAG_NAME_FUNCTIONS')

RSS_NS = {'': 'http://www.w3.org/2005/Atom'}

SUBMODULES: Final[Mapping[str, set[str | tuple[str, str]]]] = {
    'app-misc/tasksh': {'src/libshared'},
    'app-pda/tsschecker': {'external/jssy'},
    'games-emulation/citra': {
        'externals/dynarmic',
        'externals/fmt',
        'externals/lodepng/lodepng',
        'externals/sirit',
        'externals/soundtouch',
        'externals/xbyak',
    },
    'games-emulation/play': {
        'deps/CodeGen',
        'deps/Dependencies',
        'deps/Framework',
        'deps/Nuanceur',
        'deps/libchdr',
    },
    'games-emulation/rpcs3': {
        '3rdparty/asmjit/asmjit',
        '3rdparty/hidapi/hidapi',
        '3rdparty/yaml-cpp/yaml-cpp',
        '3rdparty/SoundTouch/soundtouch',
        '3rdparty/llvm/llvm',
    },
    'games-emulation/sudachi': {
        'externals/SDL',
        'externals/cpp-httplib',
        'externals/cpp-jwt',
        'externals/dynarmic',
        'externals/ffmpeg/ffmpeg',
        'externals/mbedtls',
        'externals/simpleini',
        'externals/sirit',
        'externals/xbyak',
    },
    'games-emulation/vita3k': {
        'external/LibAtrac9',
        'external/SPIRV-Cross',
        'external/VulkanMemoryAllocator-Hpp',
        'external/better-enums',
        'external/crypto-algorithms',
        'external/dlmalloc',
        'external/dynarmic',
        'external/fmt',
        'external/imgui',
        'external/imgui_club',
        'external/libfat16',
        'external/printf',
        'external/spdlog',
        'external/stb',
        'external/unicorn',
        'external/vita-toolchain',
        # TODO Handle other externals in psvpfstools https://github.com/Vita3K/psvpfstools
    },
    'games-emulation/yuzu': {
        'externals/SDL',
        'externals/cpp-jwt',
        'externals/dynarmic',
        'externals/mbedtls',
        'externals/sirit',
        ('externals/cpp-httplib', 'HTTPLIB_SHA'),
    },
    'media-sound/sony-headphones-client': {'Client/imgui'},
}
TAG_NAME_FUNCTIONS: Final[Mapping[str, Callable[[str], str]]] = {
    'app-misc/tasksh': prefix_v,
    'games-emulation/rpcs3': prefix_v,
    'games-emulation/xemu': prefix_v,
    'games-emulation/yuzu': lambda x: f'mainline-{x.replace(".", "-")}',
    'media-sound/sony-headphones-client': prefix_v,
}
