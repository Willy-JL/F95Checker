from ctypes.util import find_library
import pathlib
import sys
import re

path = pathlib.Path(__file__).absolute().parent


def find_libs(*names):
    libs = []
    for name in names:
        if lib := find_library(name):
            libs.append(lib)
    return libs


name = "F95Checker"
identifier = "io.github.willy-jl.f95checker"
script = "main.py"
debug_script = "main-debug.py"
base = None
optimize = 1
packages = ["OpenGL"]
bin_includes = []
bin_excludes = []
include_files = [
    "resources/",
    "LICENSE"
]
zip_include_packages = "*"
zip_exclude_packages = [
    "OpenGL_accelerate",
    "PyQt6",
    "glfw"
]


if sys.platform.startswith("win"):
    base = "Win32GUI"


if sys.platform.startswith("linux"):
    bin_includes += find_libs("c", "m", "ffi", "ssl", "crypto", "sqlite3")
elif sys.platform.startswith("darwin"):
    bin_includes += find_libs("intl")


icon = str(path / "resources/icons/icon")
if sys.platform.startswith("win"):
    icon += ".ico"
elif sys.platform.startswith("darwin"):
    icon += ".icns"
else:
    icon += ".png"


with open(path / script, "rb") as f:
    version = str(re.search(rb'version = "(\S+)"', f.read()).group(1), encoding="utf-8")


with open(path / debug_script, "wb") as d:
    with open(path / script, "rb") as s:
        d.write(re.sub(rb"debug = .*", rb"debug = True", s.read()))


try:
    import cx_Freeze
    cx_Freeze.setup(
        name=name,
        version=version,
        executables=[
            cx_Freeze.Executable(
                script=path / script,
                target_name=name,
                base=base,
                icon=icon
            ),
            cx_Freeze.Executable(
                script=path / debug_script,
                target_name=name + "-Debug",
                base=None,
                icon=icon
            )
        ],
        options={
            "build_exe": {
                "optimize": optimize,
                "packages": packages,
                "bin_includes": bin_includes,
                "bin_excludes": bin_excludes,
                "include_files": [path / item for item in include_files],
                "zip_include_packages": zip_include_packages,
                "zip_exclude_packages": zip_exclude_packages,
                "include_msvcr": True
            },
            "bdist_mac": {
                "iconfile": icon,
                "bundle_name": name,
                "plist_items": [
                    ("CFBundleName", name),
                    ("CFBundleDisplayName", name),
                    ("CFBundleIdentifier", identifier),
                    ("CFBundleVersion", version),
                    ("CFBundlePackageType", "APPL"),
                    ("CFBundleSignature", "????"),
                ]
            }
        },
        py_modules=[]
    )
except ModuleNotFoundError:
    print('cx_Freeze is not installed!')
    sys.exit(1)
