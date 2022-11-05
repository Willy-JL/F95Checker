from ctypes.util import find_library
import cx_Freeze
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


icon = str(path / "resources/icons/icon")
if sys.platform.startswith("win"):
    icon += ".ico"
elif sys.platform.startswith("darwin"):
    icon += ".icns"
else:
    icon += ".png"


with open(path / "modules/globals.py", "rb") as f:
    version = str(re.search(rb'version = "(\S+)"', f.read()).group(1), encoding="utf-8")


packages = ["OpenGL"]
bin_includes = []
bin_excludes = []
zip_include_packages = "*"
zip_exclude_packages = [
    "OpenGL_accelerate",
    "PyQt6",
    "glfw"
]

if sys.platform.startswith("linux"):
    bin_includes += find_libs("ffi", "ssl", "crypto")
elif sys.platform.startswith("darwin"):
    bin_includes += find_libs("intl")

if not sys.platform.startswith("win"):
    packages += ["gi"]
    bin_includes += find_libs("gtk-3", "webkit2gtk-4", "glib-2", "gobject-2")
    zip_exclude_packages += ["PyGObject"]


cx_Freeze.setup(
    name="F95Checker",
    version=version,
    executables=[
        cx_Freeze.Executable(
            script=path / "main.py",
            target_name="F95Checker",
            icon=icon
        )
    ],
    options={
        "build_exe": {
            "optimize": 1,
            "packages": packages,
            "bin_includes": bin_includes,
            "bin_excludes": bin_excludes,
            "include_files": [
                path / "resources",
                path / "LICENSE"
            ],
            "zip_include_packages": zip_include_packages,
            "zip_exclude_packages": zip_exclude_packages,
            "include_msvcr": True
        },
        "bdist_mac": {
            "iconfile": icon,
            "bundle_name": "F95Checker",
            "plist_items": [
                ("CFBundleName", "F95Checker"),
                ("CFBundleDisplayName", "F95Checker"),
                ("CFBundleIdentifier", "io.github.willy-jl.f95checker"),
                ("CFBundleVersion", version),
                ("CFBundlePackageType", "APPL"),
                ("CFBundleSignature", "????"),
            ]
        }
    },
    py_modules=[]
)
