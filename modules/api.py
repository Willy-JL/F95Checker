from modules import globals, config_utils, gui, browsers
from bs4.element import NavigableString
from bs4 import BeautifulSoup
from subprocess import Popen
from PyQt5 import QtCore
from PyQt5 import QtGui
import traceback
import pathlib
import asyncio
import aiohttp
import time
import sys
import re
import os


def get_cookie(key: str):
    """Fetch cookie value from http cookie jar"""
    for cookie in globals.http.cookie_jar:
        if cookie.key == key:
            return cookie.value
    return None


async def ask_creds():
    """Popup to get user login creds"""
    globals.gui.login_gui = gui.LoginGUI(globals.gui)
    globals.gui.login_gui.show()
    globals.gui.login_gui.setFixedSize(globals.gui.login_gui.size())
    while globals.gui.login_gui.isVisible():
        await asyncio.sleep(0.25)
    return globals.gui.login_gui.lineEdit.text(), globals.gui.login_gui.lineEdit_2.text()


async def ask_two_step_code():
    """Popup to get 2FA code"""
    globals.gui.two_step_gui = gui.TwoStepGUI(globals.gui)
    globals.gui.two_step_gui.show()
    globals.gui.two_step_gui.setFixedSize(globals.gui.two_step_gui.size())
    while globals.gui.two_step_gui.isVisible():
        await asyncio.sleep(0.25)
    return globals.gui.two_step_gui.lineEdit.text()


async def check_f95zone_error(soup, warn=False):
    """Check page html for F95Zone server difficulties and optionally warn user"""
    if soup.select_one('h1:-soup-contains("F95Zone Connection Error")') and soup.select_one('p:-soup-contains("One of our webservers appears to be experiencing difficulties")'):
        if warn:
            await gui.WarningPopup.open(globals.gui, "Connection error", "F95Zone servers are experiencing connection difficulties, please retry in a few minutes")
        return True


async def handle_no_internet():
    """Warn user of connection issues"""
    if not globals.warned_connection:
        globals.warned_connection = True
        await gui.WarningPopup.open(globals.gui, "Can't connect!", "There was an error connecting to F95Zone, please check your internet connection!")


async def login():
    """Login to F95Zone, handles both creds and 2FA"""
    if globals.logging_in:
        return
    globals.logging_in = True
    retries = 0
    while True:
        try:
            try:
                async with globals.http.head(globals.check_login_page) as check_login_req:
                    globals.logged_in = check_login_req.ok
            except aiohttp.ClientConnectorError:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                print(exc)
                await handle_no_internet()
                config_utils.save_config()
                globals.logging_in = False
                return
            break
        except Exception:
            exc = "".join(traceback.format_exception(*sys.exc_info()))
            print(exc)
            if retries >= globals.config["options"]["max_retries"]:
                await gui.WarningPopup.open(globals.gui, "Error!", f"Something went wrong...\n\n{exc}")
                config_utils.save_config()
                globals.logging_in = False
                return
            retries += 1
    retries = 0
    if not globals.token:
        while True:
            try:
                try:
                    async with globals.http.get(globals.login_page) as token_req:
                        text = await token_req.text()
                except aiohttp.ClientConnectorError:
                    exc = "".join(traceback.format_exception(*sys.exc_info()))
                    print(exc)
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
                globals.token = token_soup.select_one('input[name="_xfToken"]').get('value')
                config_utils.save_config()
                break
            except Exception:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                print(exc)
                if retries >= globals.config["options"]["max_retries"]:
                    await gui.WarningPopup.open(globals.gui, "Error!", f"Something went wrong...\n\n{exc}")
                    config_utils.save_config()
                    globals.logging_in = False
                    return
                retries += 1
    if globals.logged_in:
        config_utils.save_config()
        globals.logging_in = False
        return

    # TEMPORARY LOGIN FIX
    await gui.WarningPopup.open(globals.gui, "Login required!", "On the next window you will be prompted to login, click Ok to proceed...")
    weblogin = gui.QCookieWebEngineView()
    weblogin.resize(500, 720)
    weblogin.load(QtCore.QUrl(globals.login_page))
    weblogin.show()
    while weblogin.alive and not weblogin.cookies.get("xf_user"):
        await asyncio.sleep(0.5)
    if weblogin.alive:
        weblogin.close()
    if not weblogin.cookies.get("xf_user"):
        globals.logging_in = False
        return
    cookies = []
    globals.config["advanced"]["cookies"]["xf_csrf"] = weblogin.cookies["xf_csrf"]
    cookies.append(("xf_csrf", weblogin.cookies["xf_csrf"],))
    globals.config["advanced"]["cookies"]["xf_user"] = weblogin.cookies["xf_user"]
    cookies.append(("xf_user", weblogin.cookies["xf_user"],))
    if weblogin.cookies.get("xf_tfa_trust"):
        globals.config["advanced"]["cookies"]["xf_tfa_trust"] = weblogin.cookies["xf_tfa_trust"]
        cookies.append(("xf_tfa_trust", weblogin.cookies["xf_tfa_trust"],))
    globals.http.cookie_jar.update_cookies(cookies)
    config_utils.save_config()
    globals.logged_in = True
    globals.logging_in = False

    # ORIGINAL LOGIN CODE
    # retries_a = 0
    # while True:
    #     try:
    #         if globals.config["credentials"]["username"] == "" or globals.config["credentials"]["password"] == "":
    #             globals.config["credentials"]["username"], globals.config["credentials"]["password"] = await ask_creds()
    #             config_utils.save_config()
    #             if globals.config["credentials"]["username"] == "" or globals.config["credentials"]["password"] == "":
    #                 config_utils.save_config()
    #                 globals.logging_in = False
    #                 return
    #         try:
    #             async with globals.http.post(globals.login_endpoint, data={
    #                 "login":               globals.config["credentials"]["username"],
    #                 "url":                 "",
    #                 "password":            globals.config["credentials"]["password"],
    #                 "password_confirm":    "",
    #                 "additional_security": "",
    #                 "remember":            "1",
    #                 "_xfRedirect":         globals.domain + "/",
    #                 "website_code":        "",
    #                 "_xfToken":            globals.token
    #             }) as login_req:
    #                 if login_req.ok is False:
    #                     await gui.WarningPopup.open(globals.gui, "Error!", f"Something went wrong...\nRequest Status: {login_req.status}")
    #                 login_redirects = login_req.history
    #         except aiohttp.ClientConnectorError:
    #             exc = "".join(traceback.format_exception(*sys.exc_info()))
    #             print(exc)
    #             await handle_no_internet()
    #             config_utils.save_config()
    #             globals.logging_in = False
    #             return
    #     except Exception:
    #         exc = "".join(traceback.format_exception(*sys.exc_info()))
    #         print(exc)
    #         if retries_a >= globals.config["options"]["max_retries"]:
    #             await gui.WarningPopup.open(globals.gui, "Error!", f"Something went wrong...\n\n{exc}")
    #             break
    #         retries_a += 1
    #         continue
    #     # No redirects, bad credentials
    #     if len(login_redirects) == 0:
    #         globals.logged_in = False
    #         globals.config["credentials"]["username"], globals.config["credentials"]["password"] = await ask_creds()
    #         config_utils.save_config()
    #         if globals.config["credentials"]["username"] == "" or globals.config["credentials"]["password"] == "":
    #             config_utils.save_config()
    #             globals.logging_in = False
    #             return
    #         continue

    #     login_redirect = str(login_redirects[0].headers.get("location"))

    #     # Redirect to 2FA page
    #     if login_redirect.startswith(globals.two_step_endpoint):
    #         retries_b = 0
    #         while True:
    #             try:
    #                 two_step_code = await ask_two_step_code()
    #                 if two_step_code == "":
    #                     config_utils.save_config()
    #                     globals.logging_in = False
    #                     return
    #                 try:
    #                     async with globals.http.post(globals.two_step_endpoint, data={
    #                         "code":            two_step_code,
    #                         "trust":           "1",
    #                         "confirm":         "1",
    #                         "provider":        "totp",
    #                         "remember":        "1",
    #                         "_xfRedirect":     globals.domain + "/",
    #                         "_xfWithData":     "1",
    #                         "_xfToken":        globals.token,
    #                         "_xfResponseType": "json"
    #                     }) as two_step_req:
    #                         two_step_result = (await two_step_req.json()).get("status")
    #                 except aiohttp.ClientConnectorError:
    #                     exc = "".join(traceback.format_exception(*sys.exc_info()))
    #                     print(exc)
    #                     await handle_no_internet()
    #                     config_utils.save_config()
    #                     globals.logging_in = False
    #                     return
    #             except Exception:
    #                 exc = "".join(traceback.format_exception(*sys.exc_info()))
    #                 print(exc)
    #                 if retries_b >= globals.config["options"]["max_retries"]:
    #                     await gui.WarningPopup.open(globals.gui, "Error!", f"Something went wrong...\n\n{exc}")
    #                     break
    #                 retries_b += 1
    #                 continue
    #             if two_step_result == "ok":
    #                 globals.logged_in = True
    #                 break
    #             globals.logged_in = False
    #             continue
    #         break

    #     # Good creds, no 2FA
    #     if get_cookie('xf_session') is not None:
    #         globals.logged_in = True
    #         break
    # config_utils.save_config()
    # globals.logging_in = False


async def check_notifs():
    """Fetch alert and inbox and prompt to view if any found"""
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
                        async with globals.http.get(globals.notif_endpoint, params={"_xfToken": globals.token, "_xfResponseType": "json"}) as notif_req:
                            notif_json = await notif_req.json()
                    except aiohttp.ClientConnectorError:
                        exc = "".join(traceback.format_exception(*sys.exc_info()))
                        print(exc)
                        await handle_no_internet()
                        return
                    break
                except Exception:
                    exc = "".join(traceback.format_exception(*sys.exc_info()))
                    print(exc)
                    if retries_b >= globals.config["options"]["max_retries"]:
                        return
                    retries_b += 1
            if notif_json.get("visitor") is None:
                while globals.logging_in:
                    await asyncio.sleep(0.25)
                globals.logged_in = False
                await login()
                if globals.logged_in:
                    continue
                else:
                    return
            alerts = int(notif_json["visitor"]["alerts_unread"])
            inbox  = int(notif_json["visitor"]["conversations_unread"])
            globals.gui.refresh_bar.setValue(globals.gui.refresh_bar.value()+1)
            if globals.gui.icon_progress:
                globals.gui.icon_progress.setValue(globals.gui.icon_progress.value()+1)
            globals.gui.refresh_bar.repaint()
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
            exc = "".join(traceback.format_exception(*sys.exc_info()))
            print(exc)
            if retries_a >= globals.config["options"]["max_retries"]:
                await gui.WarningPopup.open(globals.gui, 'Error!', f'Something went wrong checking your notifications...\n\n{exc}')
                return
            retries_a += 1
            continue
        break


async def check_for_updates():
    """Update checker for the tool itself"""
    while globals.checking_updates:
        await asyncio.sleep(0.25)
    if globals.checked_updates:
        return
    globals.checking_updates = True
    if "tester" in globals.version or "dev" in globals.version:
        globals.checking_updates = False
        return
    retries = 0
    while True:
        try:
            try:
                async with globals.http.head(globals.tool_page) as check_req:
                    tool_url = str(check_req.headers.get("location"))
            except aiohttp.ClientConnectorError:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                print(exc)
                await handle_no_internet()
                globals.checking_updates = False
                return
            break
        except Exception:
            exc = "".join(traceback.format_exception(*sys.exc_info()))
            print(exc)
            if retries >= globals.config["options"]["max_retries"]:
                globals.checking_updates = False
                return
            retries += 1
    tool_version_flag = globals.version.replace(".", "-") + "-willyjl."
    if tool_url.startswith(globals.login_page):
        # Login required
        globals.logged_in = False
        while globals.logging_in:
            await asyncio.sleep(0.25)
        if not globals.logged_in:
            await login()
        if not globals.logged_in:
            globals.checking_updates = False
            return
        retries = 0
        while True:
            try:
                try:
                    async with globals.http.head(globals.tool_page) as check_req:
                        tool_url = str(check_req.headers.get("location"))
                except aiohttp.ClientConnectorError:
                    exc = "".join(traceback.format_exception(*sys.exc_info()))
                    print(exc)
                    await handle_no_internet()
                    globals.checking_updates = False
                    return
                break
            except Exception:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                print(exc)
                if retries >= globals.config["options"]["max_retries"]:
                    globals.checking_updates = False
                    return
                retries += 1
    if tool_version_flag in tool_url:
        # No update found
        globals.checked_updates = True
        globals.checking_updates = False
        return

    # Update found, log in and fetch changelog
    while globals.logging_in:
        await asyncio.sleep(0.25)
    if not globals.logged_in:
        await login()
    if not globals.logged_in:
        globals.checking_updates = False
        return
    retries = 0
    while True:
        try:
            try:
                async with globals.http.get(globals.tool_page) as tool_req:
                    text = await tool_req.text()
            except aiohttp.ClientConnectorError:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                print(exc)
                await handle_no_internet()
                globals.checking_updates = False
                return
            assert text.startswith("<!DOCTYPE html>")
            tool_html = BeautifulSoup(text, 'html.parser')
            break
        except Exception:
            exc = "".join(traceback.format_exception(*sys.exc_info()))
            print(exc)
            if retries >= globals.config["options"]["max_retries"]:
                globals.checking_updates = False
                return
            retries += 1
    if await check_f95zone_error(tool_html, warn=True):
        globals.checking_updates = False
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
            globals.checking_updates = False
            return
        globals.loop.stop()
        globals.loop.close()
        sys.exit(0)
        globals.checking_updates = False
        return
    globals.checking_updates = False


async def check(game_id):
    """Game checking"""
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
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                print(exc)
                await handle_no_internet()
                return
            if str(redirect).startswith(globals.login_page):
                # Login required
                globals.logged_in = False
                while globals.logging_in:
                    await asyncio.sleep(0.25)
                if not globals.logged_in:
                    await login()
                if not globals.logged_in:
                    return
                try:
                    async with globals.http.head(globals.config["games"][game_id]["link"]) as game_check_req:
                        redirect = game_check_req.headers.get("location")
                except aiohttp.ClientConnectorError:
                    exc = "".join(traceback.format_exception(*sys.exc_info()))
                    print(exc)
                    await handle_no_internet()
                    return

            # Fetch image if it was never downloaded
            if not os.path.isfile(f'{globals.config_path}/images/{game_id}.jpg') and not game_id in globals.image_bg_tasks:
                globals.loop.create_task(download_game_image(globals.config["games"][game_id]["link"], game_id))

            # Step Progress Bar
            globals.gui.refresh_bar.setValue(globals.gui.refresh_bar.value()+1)
            if globals.gui.icon_progress:
                globals.gui.icon_progress.setValue(globals.gui.icon_progress.value()+1)
            globals.gui.refresh_bar.repaint()

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
            exc = "".join(traceback.format_exception(*sys.exc_info()))
            print(exc)
            if retries >= globals.config["options"]["max_retries"]:
                await gui.WarningPopup.open(globals.gui, 'Error!', f'Something went wrong checking {globals.config["games"][game_id]["name"]}...\n\n{exc}')
                return
            retries += 1
            continue
        break


async def find_game_from_search_term(search_term):
    """Run quicksearch and take first result if any"""
    while globals.logging_in:
        await asyncio.sleep(0.25)
    if not globals.logged_in:
        await login()
    if not globals.logged_in:
        return None, None
    retries = 0
    while True:
        try:
            try:
                async with globals.http.post(globals.qsearch_endpoint, data={
                    "title": search_term,
                    "_xfToken": globals.token
                }) as search_req:
                    text = await search_req.text()
            except aiohttp.ClientConnectorError:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                print(exc)
                await handle_no_internet()
                return None, None
            assert text.startswith("<!DOCTYPE html>")
            search_html = BeautifulSoup(text, 'html.parser')
            if await check_f95zone_error(search_html):
                return None, None

            first_result = search_html.select_one('.quicksearch-wrapper-narrow table tr > td')

            if not first_result:
                return None, None

            title = re.sub(r"\ +", " ", first_result.get_text().replace('\n', ' ')).strip()
            link = globals.domain + first_result.select('span > a')[-1].get('href')
            return title, link

        # Retry Stuff
        except Exception:
            exc = "".join(traceback.format_exception(*sys.exc_info()))
            print(exc)
            if retries >= globals.config["options"]["max_retries"]:
                await gui.WarningPopup.open(globals.gui, 'Error!', f'Something went wrong searching {search_term}...\n\n{exc}')
                return None, None
            retries += 1
            continue
        break


async def download_game_image(source, game_id):
    """Fetch header image and save as jpg"""
    if game_id in globals.image_bg_tasks:
        return
    globals.image_bg_tasks.add(game_id)
    if isinstance(source, str):
        link = source
        while globals.logging_in:
            await asyncio.sleep(0.25)
        if not globals.logged_in:
            await login()
        if not globals.logged_in:
            globals.image_bg_tasks.remove(game_id)
            return
        retries = 0
        while True:
            try:
                try:
                    async with globals.image_semaphore:
                        async with globals.http.get(link) as thread_req:
                            text = await thread_req.text()
                            thread_req_ok = thread_req.ok
                except aiohttp.ClientConnectorError:
                    exc = "".join(traceback.format_exception(*sys.exc_info()))
                    print(exc)
                    await handle_no_internet()
                    globals.image_bg_tasks.remove(game_id)
                    return
                if not thread_req_ok:
                    globals.image_bg_tasks.remove(game_id)
                    return
                assert text.startswith("<!DOCTYPE html>")
                thread_html = BeautifulSoup(text, 'html.parser')
                if await check_f95zone_error(thread_html):
                    globals.image_bg_tasks.remove(game_id)
                    return
            # Retry Stuff
            except Exception:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                print(exc)
                if retries >= globals.config["options"]["max_retries"]:
                    globals.image_bg_tasks.remove(game_id)
                    return
                retries += 1
                continue
            break
    else:
        thread_html = source

    img_elem = thread_html.select_one(".message-threadStarterPost .message-userContent img")
    if not img_elem:
        globals.image_bg_tasks.remove(game_id)
        return
    img_link = img_elem.get('data-src').replace("thumb/", "")
    while globals.logging_in:
        await asyncio.sleep(0.25)
    if not globals.logged_in:
        await login()
    if not globals.logged_in:
        globals.image_bg_tasks.remove(game_id)
        return
    retries = 0
    while True:
        try:
            try:
                async with globals.image_semaphore:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(img_link) as img_req:
                            img_bytes = await img_req.read()
                            img_req_ok = img_req.ok
            except aiohttp.ClientConnectorError:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                print(exc)
                await handle_no_internet()
                globals.image_bg_tasks.remove(game_id)
                return
            if not img_req_ok:
                globals.image_bg_tasks.remove(game_id)
                return
            img = QtGui.QPixmap()
            img.loadFromData(img_bytes)
            pathlib.Path(f'{globals.config_path}/images').mkdir(parents=True, exist_ok=True)
            img.save(f'{globals.config_path}/images/{game_id}.jpg')
        # Retry Stuff
        except Exception:
            exc = "".join(traceback.format_exception(*sys.exc_info()))
            print(exc)
            if retries >= globals.config["options"]["max_retries"]:
                globals.image_bg_tasks.remove(game_id)
                return
            retries += 1
            continue
        break
    globals.image_bg_tasks.remove(game_id)


async def get_game_data(link):
    """Fetch game info"""
    while globals.logging_in:
        await asyncio.sleep(0.25)
    if not globals.logged_in:
        await login()
    if not globals.logged_in:
        return
    name = ""
    retries = 0
    while True:
        try:
            try:
                async with globals.http.get(link) as thread_req:
                    url = str(thread_req.url)
                    text = await thread_req.text()
                    thread_req_ok = thread_req.ok
            except aiohttp.ClientConnectorError:
                exc = "".join(traceback.format_exception(*sys.exc_info()))
                print(exc)
                await handle_no_internet()
                return
            if not thread_req_ok:
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

            # Only fetch image if adding the game or if update_image_on_game_update is enabled (enabled by default)
            game_id = link[link.rfind('.')+1:link.rfind('/')]
            if (not globals.refreshing or globals.config["options"]["update_image_on_game_update"]) and not game_id in globals.image_bg_tasks:
                globals.loop.create_task(download_game_image(thread_html, game_id))

            return {
                "name": name,
                "version": version,
                "status": status,
                "link": link,
                "changelog": changelog
            }
        # Retry Stuff
        except Exception:
            exc = "".join(traceback.format_exception(*sys.exc_info()))
            print(exc)
            if retries >= globals.config["options"]["max_retries"]:
                await gui.WarningPopup.open(globals.gui, 'Error!', f'Something went wrong checking {name}...\n\n{exc}')
                return
            retries += 1
            continue
        break
