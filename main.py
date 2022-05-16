#!/usr/bin/env python
import sys

# Mimic python's -c flag to evaluate code
if "-c" in sys.argv:
    exec(sys.argv[sys.argv.index("-c") + 1])
    sys.exit(0)


def main():
    # Must import globals first to fix load paths when frozen
    from modules import globals

    from modules.remote import singleton
    singleton.lock("F95Checker")

    from modules.remote import logger
    logger.install()

    from modules.remote import async_thread, sync_thread
    async_thread.setup()
    sync_thread.setup()

    from modules import db
    async_thread.run(db.connect(), wait=True)
    async_thread.run(db.load(), wait=True)
    async_thread.run(db.save_loop())

    from modules import gui
    globals.gui = gui.MainGUI()

    globals.gui.main_loop()

    async_thread.run(db.close(), wait=True)


if __name__ == "__main__":
    main()
