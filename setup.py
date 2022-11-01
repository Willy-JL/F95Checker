from ctypes.util import find_library
import cx_Freeze
import pathlib
import sys
import re


bin_includes = []
bin_excludes = []

def find_libs(*names):
    libs = []
    for name in names:
        if lib := find_library(name):
            libs.append(lib)
    return libs

if sys.platform.startswith("linux"):
    bin_includes += find_libs("ffi", "gtk-3", "webkit2gtk-4", "glib-2", "gobject-2", "ssl", "crypto")
elif sys.platform.startswith("darwin"):
    bin_includes += find_libs("intl")
    bin_excludes += ["libiodbc.2.dylib", "libpq.5.dylib"]

path = pathlib.Path(__file__).absolute().parent

icon = str(path / "resources/icons/icon")
if sys.platform.startswith("win"):
    icon += ".ico"
elif sys.platform.startswith("darwin"):
    icon += ".icns"
else:
    icon += ".png"

with open(path / "modules/globals.py", "rb") as f:
    version = str(re.search(rb'version = "(\S+)"', f.read()).group(1), encoding="utf-8")

cx_Freeze.setup(
    name="F95Checker",
    version=version,
    description="An update checker tool for (NSFW) games on the F95Zone platform",
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
            "packages": [
                "OpenGL",
                "gi"
            ],
            "bin_includes": bin_includes,
            "bin_excludes": bin_excludes,
            "include_files": [
                path / "resources",
                path / "LICENSE"
            ],
            "zip_include_packages": "*",
            "zip_exclude_packages": [
                "OpenGL_accelerate",
                "PyGObject",
                "PyQt6",
                "glfw"
            ],
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
