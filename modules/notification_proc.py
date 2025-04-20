import asyncio
import contextlib
import functools
import json
import sys
import typing

import desktop_notifier

from common.structs import (
    ChildPipe,
    DaemonPipe,
)

pipe: ChildPipe | DaemonPipe = None
server: asyncio.Future = None
callbacks: dict[int, typing.Callable] = {}


@contextlib.contextmanager
def setup():
    from external import async_thread
    async_thread.wait(start())
    try:
        yield
    finally:
        async_thread.wait(stop())


async def start():
    global pipe, server

    import shlex
    import subprocess
    from common.structs import DaemonPipe
    from external import async_thread
    from modules import globals

    args = []
    kwargs = dict(
        icon_uri=(globals.self_path / "resources/icons/icon.png").as_uri(),
    )

    proc = await asyncio.create_subprocess_exec(
        *shlex.split(globals.start_cmd),
        "notification-daemon",
        json.dumps(args),
        json.dumps(kwargs),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    pipe = DaemonPipe(proc)

    server = async_thread.run(_server())


async def stop():
    global pipe, server
    callbacks.clear()
    server.cancel()
    server = None
    pipe.kill()
    pipe = None


async def _server():
    from common import structs
    from modules import globals

    while True:
        try:
            data = await pipe.get_async()
        except structs.DaemonPipe.DaemonPipeExit:
            return

        try:
            event, args, kwargs = data
            if event == "callback":
                callback = callbacks.pop(args[0], globals.gui.show)
                callback()
            else:
                pass
        except Exception:
            pass


async def notify_async(
    title: str,
    msg: str,
    urgency=desktop_notifier.Urgency.Normal,
    icon: desktop_notifier.Icon = None,
    buttons: list[desktop_notifier.Button] = [],
    attachment: desktop_notifier.Attachment = None,
    timeout=5,
):
    if not await pipe.is_alive():
        await stop()
        await start()

    button_callbacks = []
    for button in buttons:
        button_callbacks.append((button.title, hash(button.on_pressed)))
        callbacks[hash(button.on_pressed)] = button.on_pressed
    button_callbacks.append(("View", 0))

    kwargs = dict(
        title=title,
        msg=msg,
        urgency=urgency.value,
        icon=icon.as_uri() if icon else None,
        button_callbacks=button_callbacks,
        on_clicked_callback=0,
        attachment=attachment.as_uri() if attachment else None,
        timeout=timeout,
    )
    pipe.put(("notify", [], kwargs))


def notify(*args, **kwargs):
    from external import async_thread
    async_thread.run(notify_async(*args, **kwargs))


def _callback(callback: int):
    pipe.put(("callback", [callback], {}))


async def _notify(
    notifier: desktop_notifier.DesktopNotifier,
    title: str,
    msg: str,
    urgency: str,
    icon: str | None,
    button_callbacks: list[tuple[str, int]],
    on_clicked_callback: int,
    attachment: str | None,
    timeout: int,
):
    await notifier.send(
        title=title,
        message=msg,
        urgency=desktop_notifier.Urgency(urgency),
        icon=desktop_notifier.Icon(uri=icon) if icon else None,
        buttons=[
            desktop_notifier.Button(
                title=button,
                on_pressed=functools.partial(_callback, callback),
            )
            for button, callback in button_callbacks
        ],
        on_clicked=functools.partial(_callback, on_clicked_callback),
        attachment=desktop_notifier.Attachment(uri=attachment) if attachment else None,
        timeout=timeout,
    )


async def _daemon(icon_uri: str):
    global pipe
    pipe = ChildPipe()

    notifier = desktop_notifier.DesktopNotifier(
        app_name="F95Checker",
        app_icon=desktop_notifier.Icon(uri=icon_uri),
    )

    while True:
        data = await pipe.get_async()

        try:
            event, args, kwargs = data
            if event == "notify":
                await _notify(notifier, *args, **kwargs)
            else:
                pass
        except Exception:
            pass


def daemon(*args, **kwargs):
    if sys.platform.startswith("darwin"):
        # Needed for desktop-notifier on MacOS
        import rubicon.objc.eventloop as cfloop
        asyncio.set_event_loop_policy(cfloop.EventLoopPolicy())

    try:
        asyncio.run(_daemon(*args, **kwargs))
    except KeyboardInterrupt:
        pass
