import sys


class Logger(object):
    def __init__(self, app_id: str):
        self.app_id = app_id
        self.console = sys.stdout

    def write(self, message):
        self.console.write(message)
        with open(f"{self.app_id}.log", "a") as log:
            log.write(message)

    def flush(self):
        self.console.flush()


def init(app_id: str):
    sys.stdout = Logger(app_id)
    sys.stderr = sys.stdout
