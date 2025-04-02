import os
import pathlib
import sys

version = "11.1"
release = False
build_number = 0
version_name = f"{version}{'' if release else ' beta'}{'' if release or not build_number else ' ' + str(build_number)}"
rpc_port = 57095
rpc_url = f"http://127.0.0.1:{rpc_port}"

frozen = getattr(sys, "frozen", False)
self_path = (pathlib.Path(sys.executable) if frozen else pathlib.Path(__file__).parent).parent
debug = not (frozen or release)
if not sys.stdout or not sys.stderr or os.devnull in (sys.stdout.name, sys.stderr.name):
    debug = False
