import json
import time
import pathlib
from modules import globals


def init_config():

    globals.config.setdefault("credentials", {})
    if True:
        globals.config["credentials"].setdefault("username", "")
        globals.config["credentials"].setdefault("password", "")

    globals.config.setdefault("options", {})
    if True:
        globals.config["options"].setdefault("browser", "")
        globals.config["options"].setdefault("private_browser", True)
        globals.config["options"].setdefault("open_html", True)
        globals.config["options"].setdefault("start_refresh", False)
        globals.config["options"].setdefault("auto_sort", "none")
        globals.config["options"].setdefault("max_retries", 3)
        globals.config["options"].setdefault("bg_mode_delay_mins", 15)
        globals.config["options"].setdefault("width", 960)
        globals.config["options"].setdefault("height", 460)

    globals.config.setdefault("style", {})
    if True:
        globals.config["style"].setdefault("back", "#181818")
        globals.config["style"].setdefault("alt", "#141414")
        globals.config["style"].setdefault("accent", "#da1e2e")
        globals.config["style"].setdefault("border", "#454545")
        globals.config["style"].setdefault("hover", "#747474")
        globals.config["style"].setdefault("disabled", "#232323")
        globals.config["style"].setdefault("radius", 6)

    globals.config.setdefault("advanced", {})
    if True:
        globals.config["advanced"].setdefault("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36")

    globals.config.setdefault("game_list", [])

    globals.config.setdefault("game_data", {})

    save_config()


def save_config():
    pathlib.Path(globals.config_path).mkdir(parents=True, exist_ok=True)
    with open(f'{globals.config_path}/f95checker.json', 'w') as f:
        json.dump(globals.config, f, indent=4)


def ensure_game_data(name):
    globals.config["game_data"].setdefault(name, {})
    if True:
        globals.config["game_data"][name].setdefault("version", '')
        globals.config["game_data"][name].setdefault("status", '')
        globals.config["game_data"][name].setdefault("installed", False)
        globals.config["game_data"][name].setdefault("played", False)
        globals.config["game_data"][name].setdefault("exe_path", '')
        globals.config["game_data"][name].setdefault("link", '')
        globals.config["game_data"][name].setdefault("add_time", time.time())
        globals.config["game_data"][name].setdefault("updated_time", 0.0)
        globals.config["game_data"][name].setdefault("changelog", '')
    save_config()


def migrate_legacy():
    from configparser import RawConfigParser
    old_config = RawConfigParser()
    old_config.read(f'{globals.config_path}/config.ini')

    try:
        globals.config["credentials"]["username"] = old_config.get('credentials', 'username', fallback='')
        globals.config["credentials"]["password"] = old_config.get('credentials', 'password', fallback='')
    except:
        pass

    save_config()

    try:
        globals.config["options"]["browser"] = old_config.get('options', 'browser', fallback='')
        globals.config["options"]["private_browser"] = old_config.getboolean('options', 'private', fallback=True)
        globals.config["options"]["open_html"] = old_config.getboolean('options', 'open_html', fallback=True)
        globals.config["options"]["start_refresh"] = old_config.getboolean('options', 'start_refresh', fallback=False)
        globals.config["options"]["auto_sort"] = old_config.get('options', 'auto_sort', fallback='none')
        globals.config["options"]["max_retries"] = old_config.getint('options', 'max_retries', fallback=5)
        globals.config["options"]["bg_mode_delay_mins"] = old_config.getint('options', 'delay', fallback=15)
        globals.config["options"]["private_browser"] = old_config.getboolean('options', 'private', fallback=True)
    except:
        pass

    save_config()

    try:
        globals.config["style"]["accent"] = old_config.get('options', 'accent', fallback='#da1e2e')
    except:
        pass

    save_config()

    try:
        globals.config["advanced"]["user_agent"] = old_config.get('advanced', 'user_agent', fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36')
    except:
        pass

    save_config()

    try:
        for game in old_config.get('games', 'game_list').split('/'):
            if not game:
                continue
            globals.config["game_list"].append(game)
    except:
        pass

    save_config()

    try:
        for section in old_config.sections():
            if section in ["credentials", "games", "options", "advanced"]:
                continue
            globals.config["game_data"].setdefault(section, {})
            if True:
                globals.config["game_data"][section].setdefault("version", old_config.get(section, 'version', fallback=''))
                globals.config["game_data"][section].setdefault("installed", old_config.getboolean(section, 'installed', fallback=False))
                globals.config["game_data"][section].setdefault("link", old_config.get(section, 'link', fallback=''))
                globals.config["game_data"][section].setdefault("add_time", old_config.getfloat(section, 'add_time', fallback=0.0))
                try:
                    globals.config["game_data"][section].setdefault("updated_time", old_config.getfloat(section, 'updated_time', fallback=0.0))
                except ValueError:
                    globals.config["game_data"][section].setdefault("updated_time", 0.0)
                globals.config["game_data"][section].setdefault("changelog", old_config.get(section, 'changelog', fallback=''))
    except:
        pass

    save_config()
