#!/usr/bin/env python


if __name__ == "__main__":
    from modules import singleton
    singleton.lock("F95Checker")

    from modules import logger
    logger.install()

    from modules import async_thread
    async_thread.setup()

    from modules import globals, gui
    globals.gui = gui.MainGUI()

    globals.gui.main_loop()
