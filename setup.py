from ctypes.util import find_library
import setuptools
import pathlib
import shutil
import sys
import re

# Friendly reminder
try:
    import cx_Freeze
    import cx_Freeze.hooks
except ModuleNotFoundError:
    print("cx_Freeze is not installed! Run: pip install -r requirements-dev.txt")
    sys.exit(1)

path = pathlib.Path(__file__).absolute().parent


# Main metadata
name = "F95Checker"
identifier = "io.github.willy-jl.f95checker"
icon = path / "resources/icons/icon"
script = path / "main.py"
debug_script = path / "main-debug.py"
version = str(re.search(rb'version = "(\S+)"', script.read_bytes()).group(1), encoding="utf-8")
debug_script.write_bytes(re.sub(rb"debug = .*", rb"debug = True", script.read_bytes()))  # Generate debug script

# Build configuration
includes = []
excludes = ["tkinter"]
packages = ["OpenGL"]
constants = []
bin_includes = []
bin_excludes = []
platform_libs = {
    "linux": ["ffi", "ssl", "crypto", "sqlite3"],
    "darwin": ["intl"]
}
include_files = [
    (path / "extension/chrome.zip",    "extension/chrome.zip"),
    (path / "extension/firefox.zip",   "extension/firefox.zip"),
    (path / "extension/integrated.js", "extension/integrated.js"),
    (path / "resources/",              "resources/"),
    (path / "LICENSE",                 "LICENSE")
]
zip_include_files = []
zip_include_packages = "*"
zip_exclude_packages = [
    "glfw",
    "bencode2",
] + (["PyQt6"] if sys.platform.startswith("win") else [])
optimize = 1
silent_level = 0
include_msvcr = True


# Add correct icon extension
if sys.platform.startswith("win"):
    icon = f"{icon}.ico"
elif sys.platform.startswith("darwin"):
    icon = f"{icon}.icns"
else:
    icon = f"{icon}.png"


# Bundle system libraries
for platform, libs in platform_libs.items():
    if sys.platform.startswith(platform):
        for lib in libs:
            if lib_path := find_library(lib):
                bin_includes.append(lib_path)


# Extension packager command
class Extension(setuptools.Command):
    """Build extension packages."""

    command_name = "extension"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        extension = pathlib.Path(__file__).parent / "extension"

        (extension / "chrome.zip").unlink(missing_ok=True)
        shutil.make_archive(extension / "chrome", "zip", extension / "chrome")

        (extension / "firefox.zip").unlink(missing_ok=True)
        shutil.make_archive(extension / "firefox", "zip", extension / "firefox")


# Actual build
cx_Freeze.setup(
    name=name,
    version=version,
    executables=[
        cx_Freeze.Executable(
            script=script,
            base="gui",
            target_name=name,
            icon=icon,
        ),
        cx_Freeze.Executable(
            script=debug_script,
            base="console",
            target_name=name + "-Debug",
            icon=icon,
        ),
    ],
    options={
        "build_exe": {
            "includes": includes,
            "excludes": excludes,
            "packages": packages,
            "constants": constants,
            "bin_includes": bin_includes,
            "bin_excludes": bin_excludes,
            "include_files": include_files,
            "zip_includes": zip_include_files,
            "zip_include_packages": zip_include_packages,
            "zip_exclude_packages": zip_exclude_packages,
            "optimize": optimize,
            "silent_level": silent_level,
            "include_msvcr": include_msvcr,
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
            ],
        },
    },
    py_modules=[],
    cmdclass={
        "extension": Extension,
    },
)
