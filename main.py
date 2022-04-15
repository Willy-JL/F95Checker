#!/usr/bin/env python
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"


def main():
    from modules import singleton
    singleton.lock("F95Checker")

    from modules import logger
    logger.install()

    from modules import async_thread
    async_thread.setup()

    from modules import db
    async_thread.run(db.connect(), wait=True)
    async_thread.run(db.load(), wait=True)

    from modules import globals, gui
    globals.gui = gui.MainGUI()

    globals.gui.main_loop()

    async_thread.run(db.close(), wait=True)


if __name__ == "__main__":
    main()
