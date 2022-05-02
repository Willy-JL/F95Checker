import cx_Freeze
import sys


base = None
if sys.platform == "win32":
    # Hide console on Windows
    base = "Win32GUI"

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
            "optimize": 2,
            "include_files": [
                "resources",
                "LICENSE"
            ],
            "include_msvcr": True
        }
    }
)
