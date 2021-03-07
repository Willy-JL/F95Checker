import os
import sys
sys.path.append(os.path.join(os.path.dirname(sys.argv[0]), "lib"))
import ctypes
ctypes.windll.kernel32.SetDllDirectoryW(os.path.join(os.path.dirname(sys.argv[0]), "lib"))
