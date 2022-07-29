import xmlrpc.server
import threading
import asyncio

from modules import globals, async_thread, callbacks, msgbox, utils
from modules.structs import MsgBox

server: xmlrpc.server.SimpleXMLRPCServer = None
thread: threading.Thread = None


def start():
    global server, thread

    def run_loop():
        try:
            server = xmlrpc.server.SimpleXMLRPCServer(("localhost", globals.rpc_port), logRequests=False, allow_none=True)
        except Exception:
            raise msgbox.Exc("RPC server error", f"Failed to start RPC server on localhost port {globals.rpc_port}. This means that the web\nbrowser extension will not work, while F95Checker itself should be unaffected.\n\nThis can often be caused by:\n - Hyper-V\n - Docker\n - Antivirus or firewall", MsgBox.warn, more=utils.get_traceback())

        server.register_function(globals.gui.show, "show_window")
        def add_game(url):
            if matches := utils.extract_thread_matches(url):
                globals.gui.show()
                async def _add_game():
                    await asyncio.sleep(0.1)
                    await callbacks.add_games(*matches)
                async_thread.run(_add_game())
        server.register_function(add_game)

        server.serve_forever()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()

