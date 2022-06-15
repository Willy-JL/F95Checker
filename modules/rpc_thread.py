import xmlrpc.server
import threading

from modules import globals, async_thread, callbacks, utils

server: xmlrpc.server.SimpleXMLRPCServer = None
thread: threading.Thread = None


def start():
    global server, thread

    def run_loop():
        server = xmlrpc.server.SimpleXMLRPCServer(("localhost", globals.rpc_port), logRequests=False, allow_none=True)
        server.register_function(globals.gui.show, "show_window")
        server.register_function(lambda url: [async_thread.run(callbacks.add_games(*utils.extract_thread_matches(url)))], "add_game")
        server.serve_forever()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()

