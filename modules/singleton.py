# https://gist.github.com/Willy-JL/2473ab16e27d4c8d8c0c4d7bcb81a5ee
import multiprocessing
import sys
import os

singleton = None


class Singleton:
    def __init__(self, app_id: str):
        if multiprocessing.current_process().name != "MainProcess":
            self.lock = None
            return
        if os.name == 'nt':
            # Requirement: pip install pywin32
            import win32api, win32event, winerror
            self.mutexname = app_id
            self.lock = win32event.CreateMutex(None, False, self.mutexname)
            self.running = (win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS)
        else:
            import fcntl
            self.lock = open(f"/tmp/instance_{app_id}.lock", 'wb')
            try:
                fcntl.lockf(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.running = False
            except IOError:
                self.running = True

        if self.running:
            raise RuntimeError(f"Another instance of {app_id} is already running!")

    def __del__(self):
        if self.lock:
            try:
                if os.name == 'nt':
                    win32api.CloseHandle(self.lock)
                else:
                    os.close(self.lock)
            except Exception:
                pass


def lock(app_id: str):
    global singleton
    if singleton is None:
        try:
            singleton = Singleton(app_id)
        except RuntimeError as exc:
            print(exc)
            sys.exit(1)
    else:
        raise FileExistsError("This instance was already assigned a singleton!")


# Example usage
if __name__ == "__main__":
    import singleton  # This script is designed as a module you import
    singleton.lock("SomeCoolProgram")

# Full credits to this answer on stackoverflow https://stackoverflow.com/a/66002139
