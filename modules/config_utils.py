from modules import globals
import pathlib
import json
import time


def init_config():
    """Fill in config with default values if they are missing"""

    globals.config.setdefault("credentials", {})
    if True:
        globals.config["credentials"].setdefault("username", "")
        globals.config["credentials"].setdefault("password", "")

    globals.config.setdefault("options", {})
    if True:
        globals.config["options"].setdefault("browser",                     ""    )
        globals.config["options"].setdefault("private_browser",             True  )
        globals.config["options"].setdefault("open_html",                   True  )
        globals.config["options"].setdefault("start_refresh",               False )
        globals.config["options"].setdefault("auto_sort",                   "none")
        globals.config["options"].setdefault("max_retries",                 3     )
        globals.config["options"].setdefault("refresh_threads",             100   )
        globals.config["options"].setdefault("bg_mode_delay_mins",          15    )
        globals.config["options"].setdefault("update_image_on_game_update", True  )

    globals.config.setdefault("style", {})
    if True:
        globals.config["style"].setdefault("back",     "#181818")
        globals.config["style"].setdefault("alt",      "#141414")
        globals.config["style"].setdefault("accent",   "#da1e2e")
        globals.config["style"].setdefault("border",   "#454545")
        globals.config["style"].setdefault("hover",    "#747474")
        globals.config["style"].setdefault("disabled", "#232323")
        globals.config["style"].setdefault("radius",   6        )

    globals.config.setdefault("advanced", {})
    if True:
        globals.config["advanced"].setdefault("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36")
        globals.config["advanced"].setdefault("cookies", {})

    globals.config.setdefault("games", {})

    if isinstance(globals.config.get("game_list"), list) and isinstance(globals.config.get("game_data"), dict):
        migrate_legacy("pre8.0")

    for game_id in globals.config["games"]:
        ensure_game_attributes(game_id)

    save_config()


def ensure_game_attributes(game_id):
    """Add default values to game if they are missing"""
    globals.config["games"][game_id].setdefault("name",         "Unknown"  )
    globals.config["games"][game_id].setdefault("version",      ""         )
    globals.config["games"][game_id].setdefault("status",       ""         )
    globals.config["games"][game_id].setdefault("installed",    False      )
    globals.config["games"][game_id].setdefault("played",       False      )
    globals.config["games"][game_id].setdefault("exe_path",     ""         )
    globals.config["games"][game_id].setdefault("link",         ""         )
    globals.config["games"][game_id].setdefault("add_time",     time.time())
    globals.config["games"][game_id].setdefault("updated_time", time.time())
    globals.config["games"][game_id].setdefault("changelog",    ""         )
    globals.config["games"][game_id].setdefault("notes",        ""         )


def save_config(filename="f95checker.json"):
    """Dump cookies and save config"""
    if globals.http:
        globals.config["advanced"]["cookies"] = {}
        for cookie in globals.http.cookie_jar:
            globals.config["advanced"]["cookies"][str(cookie.key)] = str(cookie.value)
    pathlib.Path(globals.config_path).mkdir(parents=True, exist_ok=True)
    with open(f'{globals.config_path}/{filename}', 'w') as f:
        json.dump(globals.config, f, indent=4)


def migrate_legacy(version):
    """Migrate older config versions to current"""

    if version == "pre8.0":
        save_config("pre8.0.json")
        try:
            globals.config["options"]["refresh_threads"] = 100

            for game in globals.config["game_list"]:
                if not game:
                    continue
                link = globals.config["game_data"][game]["link"]
                if not link:
                    continue
                link = globals.domain + link
                game_id = link[link.rfind(".")+1:link.rfind("/")]
                if not game_id:
                    continue
                globals.config["games"].setdefault(game_id, {})

                globals.config["games"][game_id].setdefault("name",         game                                             )
                globals.config["games"][game_id].setdefault("version",      globals.config["game_data"][game]["version"]     )
                globals.config["games"][game_id].setdefault("status",       globals.config["game_data"][game]["status"]      )
                globals.config["games"][game_id].setdefault("installed",    globals.config["game_data"][game]["installed"]   )
                globals.config["games"][game_id].setdefault("played",       globals.config["game_data"][game]["played"]      )
                globals.config["games"][game_id].setdefault("exe_path",     globals.config["game_data"][game]["exe_path"]    )
                globals.config["games"][game_id].setdefault("link",         link                                             )
                globals.config["games"][game_id].setdefault("add_time",     globals.config["game_data"][game]["add_time"]    )
                globals.config["games"][game_id].setdefault("updated_time", globals.config["game_data"][game]["updated_time"])
                globals.config["games"][game_id].setdefault("changelog",    globals.config["game_data"][game]["changelog"]   )
                globals.config["games"][game_id].setdefault("notes",        ""                                               )

            try:
                del globals.config["game_list"]
            except Exception:
                pass
            try:
                del globals.config["game_data"]
            except Exception:
                pass
            try:
                del globals.config["advanced"]["search_term_replacers"]
            except Exception:
                pass
            try:
                del globals.config["options"]["width"]
            except Exception:
                pass
            try:
                del globals.config["options"]["height"]
            except Exception:
                pass
        except Exception:
            pass

    elif version == "pre7.0":
        from configparser import RawConfigParser
        old_config = RawConfigParser()
        old_config.read(f'{globals.config_path}/config.ini')

        try:
            globals.config["credentials"]["username"] = old_config.get('credentials', 'username', fallback='')
            globals.config["credentials"]["password"] = old_config.get('credentials', 'password', fallback='')
        except Exception:
            pass

        save_config()

        try:
            globals.config["options"]["browser"]            = old_config.get(       'options', 'browser',       fallback=''    )
            globals.config["options"]["private_browser"]    = old_config.getboolean('options', 'private',       fallback=True  )
            globals.config["options"]["open_html"]          = old_config.getboolean('options', 'open_html',     fallback=True  )
            globals.config["options"]["start_refresh"]      = old_config.getboolean('options', 'start_refresh', fallback=False )
            globals.config["options"]["auto_sort"]          = old_config.get(       'options', 'auto_sort',     fallback='none')
            globals.config["options"]["max_retries"]        = old_config.getint(    'options', 'max_retries',   fallback=5     )
            globals.config["options"]["bg_mode_delay_mins"] = old_config.getint(    'options', 'delay',         fallback=15    )
            globals.config["options"]["private_browser"]    = old_config.getboolean('options', 'private',       fallback=True  )
        except Exception:
            pass

        save_config()

        try:
            globals.config["style"]["accent"] = old_config.get('options', 'accent', fallback='#da1e2e')
        except Exception:
            pass

        save_config()

        try:
            globals.config["advanced"]["user_agent"] = old_config.get('advanced', 'user_agent', fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36')
        except Exception:
            pass

        save_config()

        try:
            for game in old_config.get('games', 'game_list').split('/'):
                if not game:
                    continue
                link = old_config.get(game, 'link', fallback='')
                if not link:
                    continue
                link = globals.domain + link
                game_id = link[link.rfind(".")+1:link.rfind("/")]
                if not game_id:
                    continue
                globals.config["games"].setdefault(game_id, {})

                globals.config["games"][game_id].setdefault(    "name",         game                                                       )
                globals.config["games"][game_id].setdefault(    "version",      old_config.get       (game, 'version',      fallback=''   ))
                globals.config["games"][game_id].setdefault(    "status",       ''                                                         )
                globals.config["games"][game_id].setdefault(    "installed",    old_config.getboolean(game, 'installed',    fallback=False))
                globals.config["games"][game_id].setdefault(    "played",       False                                                      )
                globals.config["games"][game_id].setdefault(    "exe_path",     ''                                                         )
                globals.config["games"][game_id].setdefault(    "link",         link                                                       )
                globals.config["games"][game_id].setdefault(    "add_time",     old_config.getfloat  (game, 'add_time',     fallback=0.0  ))
                try:
                    globals.config["games"][game_id].setdefault("updated_time", old_config.getfloat  (game, 'updated_time', fallback=0.0  ))
                except ValueError:
                    globals.config["games"][game_id].setdefault("updated_time", 0.0)
                globals.config["games"][game_id].setdefault(    "changelog",    old_config.get       (game, 'changelog',    fallback=''   ))
                globals.config["games"][game_id].setdefault(    "notes",        ""                                                         )

            try:
                del globals.config["game_list"]
            except Exception:
                pass
            try:
                del globals.config["game_data"]
            except Exception:
                pass
            try:
                del globals.config["advanced"]["search_term_replacers"]
            except Exception:
                pass
        except Exception:
            pass

        save_config()
