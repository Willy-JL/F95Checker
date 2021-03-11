import os
import sys
import random
import asyncio
import aiohttp
from subprocess import Popen
from qasync import asyncSlot
from bs4 import BeautifulSoup
from modules import globals, api, gui
from distutils.spawn import find_executable

BROWSER_LIST = [
    "chrome",
    "firefox",
    "brave",
    "edge",
    "opera",
    "operagx"
]
BROWSER_PRIVATE_CLI_COMMANDS = {
    "chrome": "-incognito",
    "firefox": "-private-window",
    "brave": "-incognito",
    "edge": "-inprivate",
    "opera": "-private",
    "operagx": "-private"
}


def detect_user_os_and_browsers():
    user_browsers = {}

    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        exec_type = "exe"
    else:
        exec_type = "python"

    if sys.platform.startswith("linux"):
        user_os = "linux"
        if find_executable("google-chrome"):
            user_browsers["chrome"] = {"path": "google-chrome"}
        if find_executable("firefox"):
            user_browsers["firefox"] = {"path": "firefox"}
        if find_executable("brave-browser"):
            user_browsers["brave"] = {"path": "brave-browser"}
        if find_executable("opera"):
            user_browsers["opera"] = {"path": "opera"}
        # Currently (as of Sept 14 2020) OperaGX and Edge are not supported on linux
    elif sys.platform.startswith("win"):
        user_os = "windows"
        import winreg
        HKEY_LOCAL_MACHINE = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        HKEY_CURRENT_USER = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        StartMenuInternet = f"SOFTWARE\\Clients\\StartMenuInternet\\"
        open_command = f"\\shell\\open\\command"

        try:
            path = winreg.QueryValue(
                HKEY_LOCAL_MACHINE, f"{StartMenuInternet}Google Chrome{open_command}"
            )
            user_browsers["chrome"] = {"path": path}
        except FileNotFoundError:
            try:
                path = winreg.QueryValue(
                    HKEY_CURRENT_USER, f"{StartMenuInternet}Google Chrome{open_command}"
                )
                user_browsers["chrome"] = {"path": path}
            except FileNotFoundError:
                pass
        try:
            path = winreg.QueryValue(
                HKEY_LOCAL_MACHINE, f"{StartMenuInternet}Firefox-308046B0AF4A39CB{open_command}",
            )
            user_browsers["firefox"] = {"path": path}
        except FileNotFoundError:
            try:
                path = winreg.QueryValue(
                    HKEY_CURRENT_USER, f"{StartMenuInternet}Firefox-308046B0AF4A39CB{open_command}",
                )
                user_browsers["firefox"] = {"path": path}
            except FileNotFoundError:
                pass
        try:
            path = winreg.QueryValue(
                HKEY_LOCAL_MACHINE, f"{StartMenuInternet}Brave{open_command}"
            )
            user_browsers["brave"] = {"path": path}
        except FileNotFoundError:
            try:
                path = winreg.QueryValue(
                    HKEY_CURRENT_USER, f"{StartMenuInternet}Brave{open_command}"
                )
                user_browsers["brave"] = {"path": path}
            except FileNotFoundError:
                pass
        try:
            path = winreg.QueryValue(
                HKEY_LOCAL_MACHINE, f"{StartMenuInternet}Microsoft Edge{open_command}"
            )
            user_browsers["edge"] = {"path": path}
        except FileNotFoundError:
            try:
                path = winreg.QueryValue(
                    HKEY_CURRENT_USER, f"{StartMenuInternet}Microsoft Edge{open_command}"
                )
                user_browsers["edge"] = {"path": path}
            except FileNotFoundError:
                pass
        try:
            path = winreg.QueryValue(
                HKEY_LOCAL_MACHINE, f"{StartMenuInternet}OperaStable{open_command}"
            )
            user_browsers["opera"] = {"path": path}
        except FileNotFoundError:
            try:
                path = winreg.QueryValue(
                    HKEY_CURRENT_USER, f"{StartMenuInternet}OperaStable{open_command}"
                )
                user_browsers["opera"] = {"path": path}
            except FileNotFoundError:
                pass
        try:
            path = winreg.QueryValue(
                HKEY_LOCAL_MACHINE, f"{StartMenuInternet}Opera GXStable{open_command}"
            )
            user_browsers["operagx"] = {"path": path}
        except FileNotFoundError:
            try:
                path = winreg.QueryValue(
                    HKEY_CURRENT_USER, f"{StartMenuInternet}Opera GXStable{open_command}"
                )
                user_browsers["operagx"] = {"path": path}
            except FileNotFoundError:
                pass
    else:
        raise OSError()

    for browser in user_browsers:
        if user_browsers[browser]["path"][0] == '"' and user_browsers[browser]["path"][-1] == '"':
            user_browsers[browser]["path"] = user_browsers[browser]["path"][1:-1]

    return exec_type, user_os, user_browsers


async def open_webpage(link, *kw):
    if not globals.config["options"]["browser"]:
        await gui.WarningPopup.open(globals.gui, "Browser", "Please select a browser before opening a webpage!")
        return
    if link[:4] != "http":
        link = "https://f95zone.to" + link
    if globals.config["options"]["open_html"]:
        while globals.logging_in:
            await asyncio.sleep(0.25)
        if not globals.logged_in:
            await api.login()
        html_id = ''.join((random.choice('0123456789') for _ in range(8)))
        try:
            async with globals.http.get(link) as req:
                text = await req.text()
        except aiohttp.ClientConnectorError:
            await api.handle_no_internet()
            return
        assert text.startswith("<!DOCTYPE html>")
        soup = BeautifulSoup(text, 'html.parser')
        if await api.check_f95zone_error(soup, warn=True):
            return
        for tag in soup.select('link[rel="stylesheet"][href*="/css.php?css=public"]'):
            tag['href'] = 'https://f95zone.to' + tag['href']
        first_compressed = True
        for tag in soup.select('[href]'):
            if 'compressed' in str.lower(tag.text):
                if first_compressed:
                    compressed_link = tag['href']
                    compressed_code = compressed_link[compressed_link.rfind('/'):].replace('/', '#')
                    try:
                        async with globals.http.get(compressed_link) as req:
                            text = await req.text()
                    except aiohttp.ClientConnectorError:
                        await api.handle_no_internet()
                        return
                    assert text.startswith("<!DOCTYPE html>")
                    compressed_soup = BeautifulSoup(text, 'html.parser')
                    if await api.check_f95zone_error(compressed_soup, warn=True):
                        return
                    for compressed_tag in compressed_soup.select('link[rel="stylesheet"][href*="/css.php?css=public"]'):
                        compressed_tag['href'] = 'https://f95zone.to' + compressed_tag['href']
                    for compressed_tag in compressed_soup.select('[href]'):
                        if compressed_tag['href'][0] == '/':
                            compressed_tag['href'] = 'https://f95zone.to' + compressed_tag['href']
                    if not os.path.isdir('temp'):
                        os.mkdir('temp')
                    with open(f'temp/f95checkercompressed{html_id}.html', 'wb') as out:
                        out.write(compressed_soup.prettify(encoding='utf-8'))
                    tag['href'] = f'f95checkercompressed{html_id}.html{compressed_code}'
                    first_compressed = False
            elif tag['href'][0] == '/':
                tag['href'] = 'https://f95zone.to' + tag['href']
        if not os.path.isdir('temp'):
            os.mkdir('temp')
        with open(f'temp/f95checker{html_id}.html', 'wb') as out:
            out.write(soup.prettify(encoding='utf-8'))
        folder = os.getcwd().replace('\\', '/')
        link = f'file://{folder}/temp/f95checker{html_id}.html'.replace(' ', '%20')

    browser_path = globals.user_browsers[globals.config["options"]["browser"]]['path']
    private_cli_command = f'{BROWSER_PRIVATE_CLI_COMMANDS[globals.config["options"]["browser"]]}'

    if globals.config["options"]["private_browser"]:
        Popen([browser_path, private_cli_command, link])
    else:
        Popen([browser_path, link])


def open_webpage_sync_helper(link, *kw):
    globals.loop.create_task(open_webpage(link))


@asyncSlot()
async def open_webpage_async_helper(link, *kw):
    await open_webpage(link)
