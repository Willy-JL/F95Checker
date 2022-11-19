# https://gist.github.com/Willy-JL/2473ab16e27d4c8d8c0c4d7bcb81a5ee
import os


class Singleton:
    def __init__(self, app_id: str):
        if os.name == 'nt':
            # Requirement: pip install pywin32
            import win32api, win32event, winerror
            self.mutexname = app_id
            self.lock = win32event.CreateMutex(None, False, self.mutexname)
            self.running = (win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS)
        else:
            import fcntl
            self.lock = open(f"/tmp/Singleton-{app_id}.lock", 'wb')
            try:
                fcntl.lockf(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.running = False
            except IOError:
                self.running = True

        if self.running:
            raise RuntimeError(f"Another instance of {app_id} is already running!")

    def release(self):
        if self.lock:
            try:
                if os.name == 'nt':
                    win32api.CloseHandle(self.lock)
                else:
                    os.close(self.lock)
            except Exception:
                pass

    def __del__(self):
        self.release()

singletons: dict[Singleton] = {}


def lock(app_id: str):
    if app_id in singletons:
        raise FileExistsError("This app id is already locked to this process!")
    singletons[app_id] = Singleton(app_id)


def release(app_id: str):
    if app_id not in singletons:
        raise FileNotFoundError("This app id is not locked to this process!")
    singletons[app_id].release()


# Example usage
if __name__ == "__main__":
    import singleton  # This script is designed as a module you import
    singleton.lock("SomeCoolProgram")

    print("Do some very cool stuff")

    # Release usually happens automatically on exit, but call this to be sure
    singleton.release("SomeCoolProgram")

# Credits for the basic functionality go to this answer on stackoverflow https://stackoverflow.com/a/66002139
