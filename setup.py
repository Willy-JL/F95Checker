from ctypes.util import find_library
import cx_Freeze
import pathlib
import sys


base = None
if sys.platform.startswith("win"):
    # Hide console on Windows
    base = "Win32GUI"


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

cx_Freeze.setup(
    name="F95Checker",
    description="An update checker tool for (NSFW) games on the F95Zone platform",
    executables=[
        cx_Freeze.Executable(
            script=path / "main.py",
            base=base,
            target_name="F95Checker",
            icon=icon
        )
    ],
    options={
        "build_exe": {
            "optimize": 1,
            "includes": [
                "OpenGL_accelerate.numpy_formathandler"
            ],
            "packages": [
                "OpenGL_accelerate",
                "OpenGL",
                "numpy"
            ],
            "bin_includes": bin_includes,
            "include_files": [
                path / "resources",
                path / "LICENSE"
            ],
            "silent_level": 1,
            "include_msvcr": True
        },
        "bdist_mac": {
            "iconfile": icon,
            "bundle_name": "F95Checker"
        }
    }
)
