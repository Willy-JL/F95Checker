from ctypes.util import find_library
import cx_Freeze
import sys
import re
import os


base = None
if sys.platform.startswith("win"):
    # Hide console on Windows
    base = "Win32GUI"

bin_includes = []
if sys.platform.startswith("linux"):
    # Bundle libffi.so
    library = find_library("ffi")
    expr = r'%s\s+\([^\)]+\) => ([^\n]+)' % re.escape(library)
    f = os.popen('/sbin/ldconfig -p 2>/dev/null')
    data = ""
    try:
        data = f.read()
    finally:
        f.close()
    res = re.search(expr, data)
    if res:
        bin_includes.append(res.group(1))

cx_Freeze.setup(
    name="F95Checker",
    description="An update checker tool for (NSFW) games on the F95Zone platform",
    executables=[
        cx_Freeze.Executable(
            script="main.py",
            base=base,
            target_name="F95Checker",
            icon="resources/icons/icon.png"
        )
    ],
    options={
        "build_exe": {
            "build_exe": "dist",
            "optimize": 1,
            "packages": [
                "OpenGL",
            ],
            "bin_includes": bin_includes,
            "include_files": [
                "resources",
                "LICENSE"
            ],
            "include_msvcr": True
        }
    }
)
