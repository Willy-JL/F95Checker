import os


class Singleton:
    def __init__(self, app_id: str):
        if os.name == 'nt':
            import win32api
            import winerror
            import win32event
            self.mutexname = app_id
            self.lock = win32event.CreateMutex(None, False, self.mutexname)
            self.running = (win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS)
        else:
            import fcntl
            self.lock = open(f"/tmp/isnstance_{app_id}.lock", 'wb')
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
            except:
                pass
