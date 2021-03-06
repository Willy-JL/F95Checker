from ctypes.util import find_library
import cx_Freeze
import pathlib
import sys
import os
import re


bin_includes = []

def bundle_libs(*libs):
    for lib in libs:
        if name := find_library(lib):
            bin_includes.append(name)

if sys.platform.startswith("linux"):
    bundle_libs("ffi")
elif sys.platform.startswith("darwin"):
    bundle_libs("intl")

path = pathlib.Path(__file__).absolute().parent

icon = str(path / "resources/icons/icon")
if sys.platform.startswith("win"):
    icon += ".ico"
elif sys.platform.startswith("darwin"):
    icon += ".icns"
else:
    icon += ".png"

with open(path / "modules/globals.py", "rb") as f:
    version = str(re.search(rb'version = "([^\s]+)"', f.read()).group(1), encoding="utf-8")

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
                "OpenGL"
            ],
            "bin_includes": bin_includes,
            "include_files": [
                path / "resources",
                path / "LICENSE"
            ],
            "zip_include_packages": "*",
            "zip_exclude_packages": [
                "OpenGL_accelerate",
                "PyQt6",
                "glfw"
            ],
            "silent_level": 1,
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
    }
)
