#!/usr/bin/env python
import sys

# Mimic python's -c flag to evaluate code
if "-c" in sys.argv:
    eval(sys.argv[sys.argv.index("-c") + 1])
    sys.exit(0)


def main():
    # Must import globals first to fix load paths when frozen
    from modules import globals

    from modules import singleton
    singleton.lock("F95Checker")

    from modules import logger
    logger.install()

    from modules import sync_thread
    sync_thread.setup()

    from modules import async_thread
    async_thread.setup()

    from modules import db
    async_thread.run(db.connect(), wait=True)
    async_thread.run(db.load(), wait=True)

    from modules import gui
    globals.gui = gui.MainGUI()

    globals.gui.main_loop()

    async_thread.run(db.close(), wait=True)


if __name__ == "__main__":
    main()
