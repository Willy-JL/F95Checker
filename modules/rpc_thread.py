import xmlrpc.server
import threading
import asyncio

from modules import globals, async_thread, callbacks, utils

server: xmlrpc.server.SimpleXMLRPCServer = None
thread: threading.Thread = None


def start():
    global server, thread

    def run_loop():
        server = xmlrpc.server.SimpleXMLRPCServer(("localhost", globals.rpc_port), logRequests=False, allow_none=True)

        server.register_function(globals.gui.show, "show_window")
        def add_game(url):
            if matches := utils.extract_thread_matches(url):
                globals.gui.show()
                async def _add_game():
                    await asyncio.sleep(0.1)
                    await callbacks.add_games(*matches)
                async_thread.run(_add_game())
            return "success"
        server.register_function(add_game)

        server.serve_forever()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()

