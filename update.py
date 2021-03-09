import os
import sys
import time
import zipfile
import pathlib
import requests
from subprocess import Popen
from clint.textui import progress


if __name__ == '__main__':
    print(f"Pulling update from {sys.argv[1]}...\n")
    time.sleep(3)
    if len(sys.argv) == 3 and sys.argv[1][:4] == "http" and sys.argv[1][-4:] == ".zip":
        dl = requests.get(sys.argv[1], stream=True)
        with open('update.zip', 'wb') as f:
            total_length = int(dl.headers.get('content-length'))
            for chunk in progress.bar(dl.iter_content(chunk_size=1024), expected_size=(total_length/1024) + 1): 
                if chunk:
                    f.write(chunk)
                    f.flush()
        for path in list(pathlib.Path('./').rglob('*')):
            full_path = "./" + "/".join(path.parts)
            if not os.path.isdir(full_path) and not "update.py" in path.name and not "update.exe" in path.name and not "update.zip" in path.name:
                try:
                    os.remove(full_path)
                except (PermissionError, OSError, FileNotFoundError):
                    pass
        for path in list(pathlib.Path('./').rglob('*')):
            full_path = "./" + "/".join(path.parts)
            if os.path.isdir(full_path) and not "update.py" in path.name and not "update.exe" in path.name and not "update.zip" in path.name:
                try:
                    os.removedirs(full_path)
                except (PermissionError, OSError, FileNotFoundError):
                    pass
        with zipfile.ZipFile('update.zip', 'r') as z:
            for member in z.namelist():
                try:
                    z.extract(member)
                except:
                    pass
        os.remove('./update.zip')
        del dl
        Popen([sys.argv[2]])
        sys.exit(0)
