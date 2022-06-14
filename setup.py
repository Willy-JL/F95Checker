from ctypes.util import find_library
import cx_Freeze
import pathlib
import sys


if "strip" in sys.argv:
    sys.argv.remove("strip")
    import pathlib
    import shutil

    lib = next(pathlib.Path(".").glob("**/lib"))
    def remove(pattern: str):
        case_insensitive = ""
        for char in pattern:
            lower = char.lower()
            upper = char.upper()
            if lower != upper:
                case_insensitive += f"[{upper}{lower}]"
            else:
                case_insensitive += char
        for item in lib.glob(case_insensitive):
            if item.is_file():
                try:
                    item.unlink()
                except Exception:
                    pass
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)

    # Qt
    qt_remove = [
        "Bluetooth",
        "DBus",
        "Designer",
        "Help",
        "Multimedia",
        "Nfc",
        "OpenGL",
        "Qml",
        "Quick",
        "RemoteObjects",
        "Sensors",
        "SerialPort",
        "ShaderTools",
        "Sql",
        "Svg",
        "Test",
        "Wayland",
        "WebEngineQuick",
        "WebSockets",
        "WlShellIntegration",
        "XcbQpa",
        "Xml",
        "-plugin-wayland-egl",
        "-shell",
        "ga",
        "iff",
        "uiotouchplugin",
    ]
    for module in qt_remove:
        remove(f"PyQt6/**/*Qt{module}*")
        remove(f"PyQt6/**/*Qt6{module}*")
    remove("PyQt6/Qt6/translations")
    remove("PyQt6/Qt6/qsci")

    # Sources
    remove("imgui/core.cpp")
    remove("uvloop/loop.c")
    sys.exit()


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
            "silent_level": 1,
            "include_msvcr": True
        },
        "bdist_mac": {
            "iconfile": icon,
            "bundle_name": "F95Checker"
        }
    }
)
