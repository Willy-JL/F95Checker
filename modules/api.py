from modules import globals, config_utils, gui, browsers
from bs4.element import NavigableString
from bs4 import BeautifulSoup
from subprocess import Popen
import traceback
import asyncio
import aiohttp
import time
import sys
import os


def get_cookie(key: str):
    for cookie in globals.http.cookie_jar:
        if cookie.key == key:
            return cookie.value
    return None


async def ask_creds():
    globals.gui.login_gui = gui.LoginUI(globals.gui)
    globals.gui.login_gui.show()
    globals.gui.login_gui.setFixedSize(globals.gui.login_gui.size())
    while globals.gui.login_gui.isVisible():
        await asyncio.sleep(0.25)
    return globals.gui.login_gui.lineEdit.text(), globals.gui.login_gui.lineEdit_2.text()


async def check_f95zone_error(soup, warn=False):
    if soup.select_one('h1:-soup-contains("F95Zone Connection Error")') and soup.select_one('p:-soup-contains("One of our webservers appears to be experiencing difficulties")'):
        if warn:
            await gui.WarningPopup.open(globals.gui, "Connection error", "F95Zone servers are experiencing connection difficulties, please retry in a few minutes")
        return True


async def handle_no_internet():
    if not globals.warned_connection:
        globals.warned_connection = True
        await gui.WarningPopup.open(globals.gui, "Can't connect!", "There was an error connecting to F95Zone, please check your internet connection!")


async def login():
    if globals.logging_in:
        return
    globals.logging_in = True
    retries = 0
    while True:
        try:
            try:
                async with globals.http.head(globals.check_login_url) as check_login_req:
                    globals.logged_in = check_login_req.ok
            except aiohttp.ClientConnectorError:
                await handle_no_internet()
                config_utils.save_config()
                globals.logging_in = False
                return
            break
        except Exception:
            if retries >= globals.config["options"]["max_retries"]:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                await gui.WarningPopup.open(globals.gui, "Error!", f"Something went wrong...\n\n{exc}")
                config_utils.save_config()
                globals.logging_in = False
                return
            retries += 1
    retries = 0
    if not globals.config["advanced"]["token"]:
        while True:
            try:
                try:
                    async with globals.http.get(globals.login_home) as token_req:
                        text = await token_req.text()
                except aiohttp.ClientConnectorError:
                    await handle_no_internet()
                    config_utils.save_config()
                    globals.logging_in = False
                    return
                assert text.startswith("<!DOCTYPE html>")
                token_soup = BeautifulSoup(text, 'html.parser')
                if await check_f95zone_error(token_soup, warn=True):
                    config_utils.save_config()
                    globals.logging_in = False
                    return
                globals.config["advanced"]["token"] = token_soup.select_one('input[name="_xfToken"]').get('value')
                config_utils.save_config()
                break
            except Exception:
                if retries >= globals.config["options"]["max_retries"]:
                    exc = "".join(traceback.format_exception(*sys.exc_info()))
                    await gui.WarningPopup.open(globals.gui, "Error!", f"Something went wrong...\n\n{exc}")
                    config_utils.save_config()
                    globals.logging_in = False
                    return
                retries += 1
    if globals.logged_in:
        config_utils.save_config()
        globals.logging_in = False
        return
    retries = 0
    while True:
        try:
            if globals.config["credentials"]["username"] == "" or globals.config["credentials"]["password"] == "":
                globals.config["credentials"]["username"], globals.config["credentials"]["password"] = await ask_creds()
                config_utils.save_config()
                if globals.config["credentials"]["username"] == "" or globals.config["credentials"]["password"] == "":
                    config_utils.save_config()
                    globals.logging_in = False
                    return
            try:
                async with globals.http.post(globals.login_url, data={
                    "login": globals.config["credentials"]["username"],
                    "url": "",
                    "password": globals.config["credentials"]["password"],
                    "password_confirm": "",
                    "additional_security": "",
                    "remember": "1",
                    "_xfRedirect": globals.domain + "/",
                    "website_code": "",
                    "_xfToken": globals.config["advanced"]["token"]
                }) as login_req:
                    if login_req.ok is False:
                        await gui.WarningPopup.open(globals.gui, "Error!", f"Something went wrong...\nRequest Status: {login_req.status}")
            except aiohttp.ClientConnectorError:
                await handle_no_internet()
                config_utils.save_config()
                globals.logging_in = False
                return
        except Exception:
            if retries >= globals.config["options"]["max_retries"]:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                await gui.WarningPopup.open(globals.gui, "Error!", f"Something went wrong...\n\n{exc}")
                break
            retries += 1
            continue
        if get_cookie('xf_session') is not None:
            globals.logged_in = True
        else:
            globals.logged_in = False
            globals.config["credentials"]["username"], globals.config["credentials"]["password"] = await ask_creds()
            config_utils.save_config()
            if globals.config["credentials"]["username"] == "" or globals.config["credentials"]["password"] == "":
                config_utils.save_config()
                globals.logging_in = False
                return
            continue
        break
    config_utils.save_config()
    globals.logging_in = False


async def check_notifs():
    retries_a = 0
    while globals.logging_in:
        await asyncio.sleep(0.25)
    if not globals.logged_in:
        await login()
    if not globals.logged_in:
        return
    while True:
        try:
            retries_b = 0
            while True:
                try:
                    try:
                        async with globals.http.get(globals.notif_url, params={"_xfToken": globals.config["advanced"]["token"], "_xfResponseType": "json"}) as notif_req:
                            notif_json = await notif_req.json()
                    except aiohttp.ClientConnectorError:
                        await handle_no_internet()
                        return
                    break
                except Exception:
                    if retries_b >= globals.config["options"]["max_retries"]:
                        return
                    retries_b += 1
            alerts = int(notif_json["visitor"]["alerts_unread"])
            inbox  = int(notif_json["visitor"]["conversations_unread"])
            globals.gui.refresh_bar.setValue(globals.gui.refresh_bar.value()+1)
            if globals.gui.icon_progress:
                globals.gui.icon_progress.setValue(globals.gui.icon_progress.value()+1)
            if alerts != 0 and inbox != 0:
                if await gui.QuestionPopup.ask(globals.gui, 'Notifications', f'You have {alerts + inbox} unread notifications ({alerts} alert{"s" if alerts > 1 else ""} and {inbox} conversation{"s" if inbox > 1 else ""}).', "Do you want to view them?"):
                    await browsers.open_webpage(globals.alerts_page)
                    await browsers.open_webpage(globals.inbox_page )
            if alerts != 0 and inbox == 0:
                if await gui.QuestionPopup.ask(globals.gui, 'Alerts', f'You have {alerts} unread alert{"s" if alerts > 1 else ""}.', f'Do you want to view {"them" if alerts > 1 else "it"}?'):
                    await browsers.open_webpage(globals.alerts_page)
            if alerts == 0 and inbox != 0:
                if await gui.QuestionPopup.ask(globals.gui, 'Inbox', f'You have {inbox} unread conversation{"s" if inbox > 1 else ""}.', f'Do you want to view {"them" if inbox > 1 else "it"}?'):
                    await browsers.open_webpage(globals.inbox_page )
        except Exception:
            if retries_a >= globals.config["options"]["max_retries"]:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                await gui.WarningPopup.open(globals.gui, 'Error!', f'Something went wrong checking your notifications...\n\n{exc}')
                return
            retries_a += 1
            continue
        break



async def check_for_updates():
    if globals.checked_updates:
        return
    if "tester" in globals.version or "dev" in globals.version:
        return
    retries = 0
    while True:
        try:
            try:
                async with globals.http.head(globals.tool_thread) as check_req:
                    tool_url = check_req.headers.get("location")
            except aiohttp.ClientConnectorError:
                await handle_no_internet()
                return
            break
        except Exception:
            if retries >= globals.config["options"]["max_retries"]:
                return
            retries += 1
    tool_version_flag = globals.version.replace(".", "-") + "-willyjl."
    if tool_version_flag in tool_url:
        # No update found
        return

    # Update found, log in and fetch changelog
    while globals.logging_in:
        await asyncio.sleep(0.25)
    if not globals.logged_in:
        await login()
    if not globals.logged_in:
        return
    retries = 0
    while True:
        try:
            try:
                async with globals.http.get(globals.tool_thread) as tool_req:
                    text = await tool_req.text()
            except aiohttp.ClientConnectorError:
                await handle_no_internet()
                return
            assert text.startswith("<!DOCTYPE html>")
            tool_html = BeautifulSoup(text, 'html.parser')
            break
        except Exception:
            if retries >= globals.config["options"]["max_retries"]:
                return
            retries += 1
    if await check_f95zone_error(tool_html, warn=True):
        return
    tool_title = tool_html.select_one('h1[class="p-title-value"]').find(text=True, recursive=False).strip()
    tool_current = tool_title[tool_title.find('[') + 1:tool_title.find(']', tool_title.find('[') + 1)].strip()
    tool_changelog = tool_html.select_one('b:-soup-contains("Changelog") + br + div > div').get_text()
    tool_changelog = tool_changelog[tool_changelog.find(f'v{tool_current}'):tool_changelog.find(f'v{globals.version}', tool_changelog.find('\n', tool_changelog.find(f'v{tool_current}') + len(f'v{globals.version}')) + 1)]
    tool_changelog = tool_changelog.replace('Spoiler', '').strip("\n")
    # Ask to update
    globals.checked_updates = True
    if await gui.QuestionPopup.ask(globals.gui, "Update", "There is an update available for F95Checker!", "Do you want to update?", f"Changelog:\n\n{tool_changelog}"):
        latest_url = tool_html.select_one('b:-soup-contains("Current Version:") + br + a').get('href')
        if globals.exec_type == "exe":
            Popen(["update.exe", latest_url, "F95Checker.exe"])
        elif globals.exec_type == "python" and globals.user_os == "windows":
            os.system(f'start "" update.py "{latest_url}" "F95Checker.exe"')
        elif globals.exec_type == "python" and globals.user_os == "linux":
            Popen(["python3", "update.py", latest_url, "F95Checker.sh"])
        else:
            return
        globals.loop.stop()
        globals.loop.close()
        sys.exit(0)
        return


# Game Checking
async def check(game_id):
    while globals.logging_in:
        await asyncio.sleep(0.25)
    if not globals.logged_in:
        await login()
    if not globals.logged_in:
        return
    retries = 0
    while True:
        try:
            # Check for redirects
            try:
                async with globals.http.head(globals.config["games"][game_id]["link"]) as game_check_req:
                    redirect = game_check_req.headers.get("location")
            except aiohttp.ClientConnectorError:
                await handle_no_internet()
                return

            # Step Progress Bar
            globals.gui.refresh_bar.setValue(globals.gui.refresh_bar.value()+1)
            if globals.gui.icon_progress:
                globals.gui.icon_progress.setValue(globals.gui.icon_progress.value()+1)

            # Not Updated
            if not redirect:
                return

            # Updated
            game_data = await get_game_data(redirect)
            if not game_data:
                return
            old_version = globals.config["games"][game_id]["version"]

            globals.config["games"][game_id]["name"]         = game_data["name"]
            globals.config["games"][game_id]["version"]      = game_data["version"]
            globals.config["games"][game_id]["status"]       = game_data["status"]
            globals.config["games"][game_id]["installed"]    = False
            globals.config["games"][game_id]["played"]       = False
            globals.config["games"][game_id]["exe_path"]     = ""
            globals.config["games"][game_id]["link"]         = game_data["link"]
            globals.config["games"][game_id]["updated_time"] = time.time()
            globals.config["games"][game_id]["changelog"]    = game_data["changelog"]
            config_utils.save_config()

            globals.updated_games.append({
                'name': globals.config["games"][game_id]["name"],
                'old_version': old_version,
                'new_version': globals.config["games"][game_id]["version"]
            })

            globals.gui.game_list[game_id].update_details(name      = globals.config["games"][game_id]["name"],
                                                          version   = globals.config["games"][game_id]["version"],
                                                          status    = globals.config["games"][game_id]["status"],
                                                          highlight = True,
                                                          installed = False,
                                                          played    = False,
                                                          link      = globals.config["games"][game_id]["link"])
        # Retry Stuff
        except Exception:
            if retries >= globals.config["options"]["max_retries"]:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                await gui.WarningPopup.open(globals.gui, 'Error!', f'Something went wrong checking {globals.config["games"][game_id]["name"]}...\n\n{exc}')
                return
            retries += 1
            continue
        break


# Fetch game info
async def get_game_data(link):
    while globals.logging_in:
        await asyncio.sleep(0.25)
    if not globals.logged_in:
        await login()
    if not globals.logged_in:
        return
    retries = 0
    while True:
        try:
            try:
                async with globals.http.get(link) as thread_req:
                    url = str(thread_req.url)
                    text = await thread_req.text()
            except aiohttp.ClientConnectorError:
                await handle_no_internet()
                return
            assert text.startswith("<!DOCTYPE html>")
            thread_html = BeautifulSoup(text, 'html.parser')
            if await check_f95zone_error(thread_html):
                return

            title = thread_html.select_one('h1[class="p-title-value"]').find(text=True, recursive=False).strip()
            name = title[:title.find("[")].strip() if "[" in title else title.strip()
            if title.count('[') >= 2 or title.count(']') >= 2:
                version = title[title.find('[') + 1:title.find(']', title.find('[') + 1)].strip()
            else:
                version_item = thread_html.select_one('b:-soup-contains("Version")')
                version = version_item.next_sibling if version_item else ""
                if isinstance(version, NavigableString):
                    version = str(version)
                    version = version[2:] if version.startswith(": ") else version
                else:
                    version = "N/A"
            if len(thread_html.select('h1[class="p-title-value"] > a > span:-soup-contains("[Completed]")')) > 0:
                status = 'completed'
            elif len(thread_html.select('h1[class="p-title-value"] > a > span:-soup-contains("[Onhold]")')) > 0:
                status = 'onhold'
            elif len(thread_html.select('h1[class="p-title-value"] > a > span:-soup-contains("[Abandoned]")')) > 0:
                status = 'abandoned'
            else:
                status = 'none'
            link = url
            changelog = thread_html.select_one('b:-soup-contains("Changelog") + br + div > div')
            if changelog is None:
                changelog = thread_html.select_one('b:-soup-contains("Change-Log") + br + div > div')
            if changelog is None:
                changelog = ""
            else:
                changelog = changelog.get_text().replace('Spoiler', '')
                changelog = changelog[:changelog.replace('\n', ' ', 69).find('\n')].strip("\n")
                while "\n\n\n" in changelog:
                    changelog = changelog.replace('\n\n\n', '\n\n')
            return {
                "name": name,
                "version": version,
                "status": status,
                "link": link,
                "changelog": changelog
            }
        # Retry Stuff
        except Exception:
            if retries >= globals.config["options"]["max_retries"]:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                await gui.WarningPopup.open(globals.gui, 'Error!', f'Something went wrong checking {name}...\n\n{exc}')
                return
            retries += 1
            continue
        break