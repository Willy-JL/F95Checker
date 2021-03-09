import os
import sys
import time
import aiohttp
import asyncio
import traceback
from subprocess import Popen
from bs4 import BeautifulSoup
from modules import globals, config_utils, gui, browsers


def get_cookie(key: str):
    for cookie in globals.http.cookie_jar:
        if cookie.key == key:
            return cookie.value
    return None


async def ask_creds():
    globals.gui.login_gui = gui.LoginUI(globals.gui)
    globals.gui.login_gui.show()
    globals.gui.login_gui.setFixedSize(globals.gui.login_gui.size())
    while globals.gui.login_gui.alive:
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
    if not globals.token:
        while True:
            try:
                try:
                    async with globals.http.get('https://f95zone.to/login/') as token_req:
                        text = await token_req.text()
                except aiohttp.ClientConnectorError:
                    await handle_no_internet()
                    globals.logging_in = False
                    return
                assert text.startswith("<!DOCTYPE html>")
                token_soup = BeautifulSoup(text, 'html.parser')
                if await check_f95zone_error(token_soup, warn=True):
                    globals.logging_in = False
                    return
                globals.token = token_soup.select_one('input[name="_xfToken"]').get('value')
                break
            except:
                if retries >= globals.config["options"]["max_retries"]:
                    exc = "".join(traceback.format_exception(*sys.exc_info()))
                    await gui.WarningPopup.open(globals.gui, "Error!", f"Something went wrong...\n\n{exc}")
                    globals.logging_in = False
                    return
                retries += 1
    retries = 0
    while True:
        try:
            if globals.config["credentials"]["username"] == "" or globals.config["credentials"]["password"] == "":
                globals.config["credentials"]["username"], globals.config["credentials"]["password"] = await ask_creds()
                config_utils.save_config()
            try:
                async with globals.http.post(globals.login_url, data={
                    "login": globals.config["credentials"]["username"],
                    "url": "",
                    "password": globals.config["credentials"]["password"],
                    "password_confirm": "",
                    "additional_security": "",
                    "remember": "1",
                    "_xfRedirect": "https://f95zone.to/",
                    "website_code": "",
                    "_xfToken": globals.token
                }) as login_req:
                    if login_req.ok is False:
                        await gui.WarningPopup.open(globals.gui, "Error!", f"Something went wrong...\nRequest Status: {login_req.status}")
            except aiohttp.ClientConnectorError:
                await handle_no_internet()
                globals.logging_in = False
                return
        except:
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
            continue
        break
    globals.logging_in = False


async def check_notifs():
    retries_a = 0
    while globals.logging_in:
        await asyncio.sleep(0.25)
    if not globals.logged_in:
        await login()
    if globals.logged_in:
        while True:
            try:
                retries_b = 0
                while True:
                    try:
                        try:
                            async with globals.http.get(globals.notif_url, params={"_xfToken": globals.token, "_xfResponseType": "json"}) as notif_req:
                                notif_json = await notif_req.json()
                        except aiohttp.ClientConnectorError:
                            await handle_no_internet()
                            return
                        break
                    except ArithmeticError:
                        if retries_b >= globals.config["options"]["max_retries"]:
                            return
                        retries_b += 1
                alerts = int(notif_json["visitor"]["alerts_unread"])
                inbox = int(notif_json["visitor"]["conversations_unread"])
                globals.gui.refresh_bar.setValue(globals.gui.refresh_bar.value()+1)
                if alerts != 0 and inbox != 0:
                    if await gui.QuestionPopup.ask(globals.gui, 'Notifications', f'You have {int(alerts) + int(inbox)} unread notifications ({alerts} alert{"s" if int(alerts) > 1 else ""} and {inbox} conversation{"s" if int(inbox) > 1 else ""}).', "Do you want to view them?"):
                        await browsers.open_webpage('https://f95zone.to/account/alerts')
                        await browsers.open_webpage('https://f95zone.to/conversations/')
                if alerts != 0 and inbox == 0:
                    if await gui.QuestionPopup.ask(globals.gui, 'Alerts', f'You have {alerts} unread alert{"s" if int(alerts) > 1 else ""}.', f'Do you want to view {"them" if int(alerts) > 1 else "it"}?'):
                        await browsers.open_webpage('https://f95zone.to/account/alerts')
                if alerts == 0 and inbox != 0:
                    if await gui.QuestionPopup.ask(globals.gui, 'Inbox', f'You have {inbox} unread conversation{"s" if int(inbox) > 1 else ""}.', f'Do you want to view {"them" if int(inbox) > 1 else "it"}?'):
                        await browsers.open_webpage('https://f95zone.to/conversations/')
            except ArithmeticError:
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
                async with globals.http.get('https://f95zone.to/forums/tools-tutorials.17/', params={'starter_id': '1276534'}) as check_req:
                    text = await check_req.text()
            except aiohttp.ClientConnectorError:
                await handle_no_internet()
                return
            assert text.startswith("<!DOCTYPE html>")
            check_soup = BeautifulSoup(text, 'html.parser')
            break
        except:
            if retries >= globals.config["options"]["max_retries"]:
                return
            retries += 1
    if await check_f95zone_error(check_soup, warn=True):
        return
    tool_thread = check_soup.select_one('div[class="structItemContainer-group js-threadList"] > div > div[class="structItem-cell structItem-cell--main"] > div[class="structItem-title"] > a[data-tp-primary="on"]')
    tool_title = tool_thread.get_text()
    tool_current = tool_title[tool_title.find('[') + 1:tool_title.find(']', tool_title.find('[') + 1)]
    if not globals.version == tool_current:
        # Update found, log in and fetch changelog
        while globals.logging_in:
            await asyncio.sleep(0.25)
        if not globals.logged_in:
            await login()
        if globals.logged_in:
            retries = 0
            while True:
                try:
                    try:
                        async with globals.http.get('https://f95zone.to/threads/44173/') as tool_req:
                            text = await tool_req.text()
                    except aiohttp.ClientConnectorError:
                        await handle_no_internet()
                        return
                    assert text.startswith("<!DOCTYPE html>")
                    tool_soup = BeautifulSoup(text, 'html.parser')
                    break
                except:
                    if retries >= globals.config["options"]["max_retries"]:
                        return
                    retries += 1
            if await check_f95zone_error(tool_soup, warn=True):
                return
            tool_changelog = tool_soup.select_one('b:-soup-contains("Changelog") + br + div > div').get_text()
            changes = tool_changelog[tool_changelog.find(f'v{tool_current}'):tool_changelog.find(
                f'v{globals.version}', tool_changelog.find('\n', tool_changelog.find(f'v{tool_current}') + len(f'v{globals.version}')) + 1)]
            changes = changes.replace('Spoiler', '')
            try:
                while changes[-1] == '\n':
                    changes = changes[:-1]
            except IndexError:
                pass
            try:
                while changes[0] == '\n':
                    changes = changes[1:]
            except IndexError:
                pass
            # Ask to update
            globals.checked_updates = True
            if await gui.QuestionPopup.ask(globals.gui, "Update", "There is an update available for F95Checker!", "Do you want to update?", f"Changelog:\n\n{changes}"):
                latest_url = tool_soup.select_one('b:-soup-contains("Current Version:") + br + a').get('href')
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
async def check(name):
    while globals.logging_in:
        await asyncio.sleep(0.25)
    if not globals.logged_in:
        await login()
    if globals.logged_in:
        retries = 0
        while True:
            try:
                config_utils.ensure_game_data(name)
                # Search Request
                if name == 'Life':
                    search_term = "Fasder"
                elif name == 'Big Bad Principal':
                    search_term = "Big Bad  Principal"
                elif name == 'Life With a Slave -Teaching Feeling-':
                    search_term = "Life With a Slave  -Teaching Feeling-"
                else:
                    search_term = name
                try:
                    async with globals.http.post(globals.search_url, data={"title": search_term, "_xfToken": globals.token}) as game_check_req:
                        text = await game_check_req.text()
                except aiohttp.ClientConnectorError:
                    await handle_no_internet()
                    return
                assert text.startswith("<!DOCTYPE html>")
                result_html = BeautifulSoup(text, 'html.parser')
                if await check_f95zone_error(result_html):
                    return
                # Step Progress Bar
                globals.gui.refresh_bar.setValue(globals.gui.refresh_bar.value()+1)
                # Check number of search results
                if len(result_html.select(f'div[class="quicksearch-wrapper-wide"] > div > div > div > div[data-xf-init="responsive-data-list"] > table > tr[class="dataList-row dataList-row--noHover"] > td[class="dataList-cell"] > span > a:-soup-contains("{name}")')) == 0:
                    await gui.WarningPopup.open(globals.gui, 'Error!', f'Couldn\'t find \"{name}\"...')
                    return
                found = False
                thread_item = ''
                title = ''
                # Find right search result
                for item in result_html.select(f'div[class="quicksearch-wrapper-wide"] > div > div > div > div[data-xf-init="responsive-data-list"] > table > tr[class="dataList-row dataList-row--noHover"] > td[class="dataList-cell"] > span > a:-soup-contains("{name}")'):
                    title = item.get_text()
                    result_name = title[0:title.find('[')]
                    if result_name[-1] == ' ':
                        result_name = result_name[:-1]
                    if result_name == name:
                        found = True
                        thread_item = item
                        break
                    else:
                        pass
                if not found:
                    await gui.WarningPopup.open(globals.gui, 'Error!', f'Couldn\'t find \"{name}\"...')
                    return
                cur_link = thread_item.get('href')
                globals.gui.game_list[name].update_details(link=cur_link)
                # Changelog fetcher
                changelog_fetched = False
                if globals.config["game_data"][name]["changelog"] == '' or globals.config["game_data"][name]["status"] == '':
                    try:
                        try:
                            async with globals.http.get(url='https://f95zone.to' + cur_link) as changelog1_req:
                                text = await changelog1_req.text()
                        except aiohttp.ClientConnectorError:
                            await handle_no_internet()
                            return
                        assert text.startswith("<!DOCTYPE html>")
                        page_html = BeautifulSoup(text, 'html.parser')
                        if await check_f95zone_error(page_html):
                            return
                        if len(page_html.select('h1[class="p-title-value"] > a > span:-soup-contains("[Completed]")')) > 0:
                            globals.config["game_data"][name]["status"] = 'completed'
                        elif len(page_html.select('h1[class="p-title-value"] > a > span:-soup-contains("[Onhold]")')) > 0:
                            globals.config["game_data"][name]["status"] = 'onhold'
                        elif len(page_html.select('h1[class="p-title-value"] > a > span:-soup-contains("[Abandoned]")')) > 0:
                            globals.config["game_data"][name]["status"] = 'abandoned'
                        else:
                            globals.config["game_data"][name]["status"] = 'none'
                        config_utils.save_config()
                        globals.gui.game_list[name].update_details(status=globals.config["game_data"][name]["status"])
                        try:
                            game_changelog = page_html.select_one('b:-soup-contains("Changelog") + br + div > div').get_text()
                        except AttributeError:
                            game_changelog = page_html.select_one('b:-soup-contains("Change-Log") + br + div > div').get_text()
                        game_changelog = game_changelog.replace('Spoiler', '')
                        game_changes = game_changelog[:game_changelog.replace('\n', '', 69).find('\n')]
                        try:
                            while game_changes[-1] == '\n':
                                game_changes = game_changes[:-1]
                        except:
                            pass
                        try:
                            while game_changes[0] == '\n':
                                game_changes = game_changes[1:]
                        except:
                            pass
                        changelog = game_changes
                        while changelog.__contains__('\n\n\n'):
                            changelog = changelog.replace('\n\n\n', '\n\n')
                        globals.config["game_data"][name]["changelog"] = changelog
                        config_utils.save_config()
                        changelog_fetched = True
                    except:
                        pass
                # Version Management
                if title.count('[') < 2 or title.count(']') < 2:
                    cur_version = "N/A"
                else:
                    cur_version = title[title.find('[') + 1:title.find(']', title.find('[') + 1)].strip()
                # Not Updated
                if cur_version == globals.config["game_data"][name]["version"]:
                    return
                # Updated
                if cur_version != "N/A":
                    globals.updated_games.append({'name': name, 'old_version': globals.config["game_data"][name]["version"], 'new_version': cur_version})
                globals.config["game_data"][name]["link"] = cur_link
                globals.config["game_data"][name]["version"] = cur_version
                if cur_version != "N/A":
                    globals.config["game_data"][name]["updated_time"] = time.time()
                    globals.config["game_data"][name]["installed"] = False
                    globals.config["game_data"][name]["played"] = False
                    globals.config["game_data"][name]["exe_path"] = ""
                config_utils.save_config()
                if cur_version != "N/A":
                    globals.gui.game_list[name].update_details(highlight=True,
                                                               installed=False,
                                                               played=False,
                                                               version=cur_version)
                else:
                    globals.gui.game_list[name].update_details(version=cur_version)
                # Changelog Fetcher
                if not changelog_fetched:
                    try:
                        try:
                            async with globals.http.get(url='https://f95zone.to' + cur_link) as changelog2_req:
                                text = await changelog2_req.text()
                        except aiohttp.ClientConnectorError:
                            await handle_no_internet()
                            return
                        assert text.startswith("<!DOCTYPE html>")
                        page_html = BeautifulSoup(text, 'html.parser')
                        if await check_f95zone_error(page_html):
                            return
                        if len(page_html.select('h1[class="p-title-value"] > a > span:-soup-contains("[Completed]")')) > 0:
                            globals.config["game_data"][name]["status"] = 'completed'
                        elif len(page_html.select('h1[class="p-title-value"] > a > span:-soup-contains("[Onhold]")')) > 0:
                            globals.config["game_data"][name]["status"] = 'onhold'
                        elif len(page_html.select('h1[class="p-title-value"] > a > span:-soup-contains("[Abandoned]")')) > 0:
                            globals.config["game_data"][name]["status"] = 'abandoned'
                        else:
                            globals.config["game_data"][name]["status"] = 'none'
                        config_utils.save_config()
                        globals.gui.game_list[name].update_details(status=globals.config["game_data"][name]["status"])
                        try:
                            game_changelog = page_html.select_one('b:-soup-contains("Changelog") + br + div > div').get_text()
                        except AttributeError:
                            game_changelog = page_html.select_one('b:-soup-contains("Change-Log") + br + div > div').get_text()
                        game_changelog = game_changelog.replace('Spoiler', '')
                        game_changes = game_changelog[:game_changelog.replace('\n', '', 69).find('\n')]
                        try:
                            while game_changes[-1] == '\n':
                                game_changes = game_changes[:-1]
                        except:
                            pass
                        try:
                            while game_changes[0] == '\n':
                                game_changes = game_changes[1:]
                        except:
                            pass
                        changelog = game_changes
                        while changelog.__contains__('\n\n\n'):
                            changelog = changelog.replace('\n\n\n', '\n\n')
                        globals.config["game_data"][name]["changelog"] = changelog
                        config_utils.save_config()
                        changelog_fetched = True
                    except:
                        pass
            # Retry Stuff
            except:
                if retries >= globals.config["options"]["max_retries"]:
                    exc = "".join(traceback.format_exception(*sys.exc_info()))
                    await gui.WarningPopup.open(globals.gui, 'Error!', f'Something went wrong checking {name}...\n\n{exc}')
                    return
                retries += 1
                continue
            break
