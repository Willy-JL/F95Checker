from common import meta

def apply():
    # Create dummy IO streams if missing
    import os
    import sys
    if not sys.stdout: sys.stdout = open(os.devnull, "w")
    if not sys.stderr: sys.stderr = open(os.devnull, "w")

    # Fix frozen load paths
    if meta.frozen:
        if sys.platform.startswith("linux"):
            session_type = os.environ.get('XDG_SESSION_TYPE')
            if session_type in ("x11", "wayland"):
                library = meta.self_path / f"lib/glfw/{session_type}/libglfw.so"
                if library.is_file():
                    os.environ["PYGLFW_LIBRARY"] = str(library)
        elif sys.platform.startswith("darwin"):
            process = meta.self_path.parent / "Helpers/QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess"
            if process.is_file():
                os.environ["QTWEBENGINEPROCESS_PATH"] = str(process)

    # Pillow image loading fixes
    import pillow_avif
    from PIL import ImageFile, PngImagePlugin
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    PngImagePlugin.MAX_TEXT_CHUNK *= 10

    # Optimize OpenGL
    import glfw
    import OpenGL
    glfw.ERROR_REPORTING = meta.debug
    for option in ("ERROR_LOGGING", "ERROR_CHECKING", "CONTEXT_CHECKING"):
        setattr(OpenGL, option, meta.debug)
    if meta.debug:
        import logging
        glfw.ERROR_REPORTING = {
            65548: "ignore",  # Wayland: The platform does not support window position/icon
            None: "raise",
        }
        logging.basicConfig()

    # Register archive formats
    import py7zr
    import rarfile
    import shutil
    import zipfile_deflate64
    shutil.register_unpack_format("7zip", [".7z"], py7zr.unpack_7zarchive)
    def unpack_rarfile(archive, path):
        if not rarfile.is_rarfile(archive):
            raise shutil.ReadError(f"{archive} is not a RAR file.")
        with rarfile.RarFile(archive) as arc:
            arc.extractall(path)
    try:
        if rarfile.tool_setup():
            shutil.register_unpack_format("rar", [".rar"], unpack_rarfile)
    except rarfile.RarCannotExec:
        pass
