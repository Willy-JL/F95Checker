import asyncio
import contextlib
import http.server
import json
import socketserver
import threading

from common.structs import (
    MsgBox,
    Tab,
)
from external import (
    async_thread,
    error,
)
from modules import (
    callbacks,
    colors,
    globals,
    icons,
    msgbox,
    utils,
)

server: socketserver.TCPServer = None
thread: threading.Thread = None


@contextlib.contextmanager
def setup():
    if globals.settings.rpc_enabled:
        start()
    try:
        yield
    finally:
        stop()


def start():
    global thread

    def run_loop():
        global server

        mdi_webfont = icons.font_path.read_bytes()

        class RPCHandler(http.server.SimpleHTTPRequestHandler):
            if not globals.debug:
                log_message = lambda *_, **__: None

            def do_OPTIONS(self):
                self.send_response(200, "ok")
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header("Access-Control-Allow-Headers", "X-Requested-With")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def send_resp(self, code: int, content_type: str = "application/octet-stream", headers: dict[str, str] = {}):
                self.send_response(code)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", content_type)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()

            def send_json(self, code: int, data: list | dict):
                self.send_resp(code, "application/json")
                self.wfile.write(json.dumps(data).encode())

            def do_GET(self):
                try:
                    match self.path:
                        case "/games":
                            self.send_json(200, [
                                {
                                    "id": g.id,
                                    "icon": g.tab.icon if g.tab else Tab.first_tab_label()[0],
                                    "color": colors.rgba_0_1_to_hex(g.tab.color) if g.tab and g.tab.color else "#FD5555",
                                    "notes": g.notes,
                                }
                                for g in globals.games.values()
                            ])
                            return
                        case "/settings":
                            self.send_json(200, {
                                "icon_glow": globals.settings.ext_icon_glow,
                                "highlight_tags": globals.settings.ext_highlight_tags,
                                "tags_highlights": {t.text: h.value for t, h in globals.settings.tags_highlights.items()},
                            })
                            return
                        case "/assets/mdi-webfont.ttf":
                            self.send_resp(200, "font/ttf", headers={"Cache-Control": "public, max-age=3600"})
                            self.wfile.write(mdi_webfont)
                            return
                        case _:
                            self.send_resp(404)
                            return
                    self.send_resp(200)
                except Exception:
                    self.send_resp(500)

            def do_POST(self):
                try:
                    match self.path:
                        case "/window/show":
                            globals.gui.show()
                        case "/window/hide":
                            globals.gui.hide()
                        case "/window/refresh_styles":
                            globals.gui.load_styles_from_toml()
                            globals.gui.refresh_styles()
                        case "/games/add":
                            urls = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                            if matches := utils.extract_thread_matches("\n".join(urls)):
                                if not globals.settings.ext_background_add:
                                    globals.gui.show()
                                async def _add_game():
                                    await asyncio.sleep(0.1)
                                    await callbacks.add_games(*matches)
                                async_thread.run(_add_game())
                        case _:
                            self.send_resp(404)
                            return
                    self.send_resp(200)
                except Exception:
                    self.send_resp(500)

        try:
            socketserver.TCPServer.allow_reuse_address = True
            socketserver.TCPServer.allow_reuse_port = True
            server = socketserver.TCPServer(("127.0.0.1", globals.rpc_port), RPCHandler)
        except Exception:
            raise msgbox.Exc(
                "RPC server error",
                f"Failed to start RPC server on localhost port {globals.rpc_port}:\n{error.text()}\n"
                "\n"
                "This means that the web browser extension will not work, while F95Checker\n"
                "itself should be unaffected. Some common causes are:\n"
                " - Hyper-V\n"
                " - Docker\n"
                " - Antivirus or firewall",
                MsgBox.warn,
                more=error.traceback()
            )

        server.serve_forever()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()


def stop():
    global server, thread
    if thread is not None and thread.is_alive() and server is not None:
        server.shutdown()
        server.server_close()
        thread.join()
    server = None
    thread = None
