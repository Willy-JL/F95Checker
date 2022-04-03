from modules.structs import *
from modules import globals
import aiosqlite
import asyncio
import json

connection: aiosqlite.Connection = None
available: bool = False
pending: int = 0


async def _wait_connection():
    while not available:
        await asyncio.sleep(0.1)


async def wait_connection():
    await asyncio.wait_for(_wait_connection(), timeout=30)


async def _wait_pending():
    while pending > 0:
        await asyncio.sleep(0.1)


async def wait_pending():
    await asyncio.wait_for(_wait_pending(), timeout=30)


async def connect():
    global available, connection

    connection = await aiosqlite.connect(globals.data_path / "db.sqlite3")
    connection.row_factory = aiosqlite.Row  # Return sqlite3.Row instead of tuple

    await connection.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            _                           INTEGER PRIMARY KEY CHECK (_=0),
            browser_custom_arguments    TEXT    DEFAULT "",
            browser_custom_executable   TEXT    DEFAULT "",
            browser_html                INTEGER DEFAULT 0,
            browser_private             INTEGER DEFAULT 0,
            browser                     INTEGER DEFAULT 0,
            column_installed            INTEGER DEFAULT 1,
            column_last_played          INTEGER DEFAULT 0,
            column_last_updated         INTEGER DEFAULT 0,
            column_name                 INTEGER DEFAULT 1,
            column_played               INTEGER DEFAULT 1,
            column_rating               INTEGER DEFAULT 0,
            column_status               INTEGER DEFAULT 1,
            column_time_added           INTEGER DEFAULT 0,
            column_version              INTEGER DEFAULT 1,
            refresh_completed_games     INTEGER DEFAULT 1,
            refresh_workers             INTEGER DEFAULT 20,
            request_timeout             INTEGER DEFAULT 30,
            select_executable_after_add INTEGER DEFAULT 0,
            sort_mode                   INTEGER DEFAULT 1,
            start_in_tray               INTEGER DEFAULT 0,
            start_refresh               INTEGER DEFAULT 0,
            start_with_system           INTEGER DEFAULT 0,
            style_accent                TEXT    DEFAULT "#da1e2e",
            style_alt_bg                TEXT    DEFAULT "#141414",
            style_bg                    TEXT    DEFAULT "#181818",
            style_btn_border            TEXT    DEFAULT "#454545",
            style_btn_disabled          TEXT    DEFAULT "#232323",
            style_btn_hover             TEXT    DEFAULT "#747474",
            style_corner_radius         INTEGER DEFAULT 6,
            style_scaling               REAL    DEFAULT 1.0,
            tray_refresh_interval       INTEGER DEFAULT 15,
            update_keep_executable      INTEGER DEFAULT 0,
            update_keep_image           INTEGER DEFAULT 0
        )
    """)
    await connection.execute("""
        INSERT INTO settings
        (_)
        VALUES
        (0)
        ON CONFLICT DO NOTHING
    """)

    await connection.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id           INTEGER PRIMARY KEY,
            name         TEXT    DEFAULT "",
            version      TEXT    DEFAULT "",
            status       INTEGER DEFAULT 0,
            url          TEXT    DEFAULT "",
            time_added   INTEGER DEFAULT 0,
            last_updated INTEGER DEFAULT 0,
            last_checked INTEGER DEFAULT 0,
            last_played  INTEGER DEFAULT 0,
            rating       INTEGER DEFAULT 0,
            installed    TEXT    DEFAULT "",
            played       INTEGER DEFAULT 0,
            executable   TEXT    DEFAULT "",
            description  TEXT    DEFAULT "",
            changelog    TEXT    DEFAULT "",
            tags         TEXT    DEFAULT "[]",
            notes        TEXT    DEFAULT ""
        )
    """)

    available = True


# Committing should save to disk, but for some reason it only does so after closing
async def save_to_disk(reconnect_after=True):
    global available
    available = False
    await wait_pending()
    await connection.commit()
    await connection.close()
    if reconnect_after:
        await connect()


async def execute(request, *args):
    global pending
    await wait_connection()
    pending += 1
    try:
        return await connection.execute(request, *args)
    finally:
        pending -= 1


async def setup():
    globals.settings = Settings()
    cursor = await execute("""
        SELECT *
        FROM settings
    """)
    settings = await cursor.fetchone()
    for key in settings.keys():
        data_type = Settings.__annotations__[key]
        value = data_type(settings[key])
        setattr(globals.settings, key, value)

    globals.games = dict()
    cursor = await execute("""
        SELECT *
        FROM games
    """)
    games = await cursor.fetchall()
    for game in games:
        globals.games[game["id"]] = Game()
        for key in game.keys():
            data_type = Game.__annotations__[key]
            if data_type == list[Tag]:
                value = [Tag(x) for x in json.loads(game[key])]
            else:
                value = data_type(game[key])
            setattr(globals.games[game["id"]], key, value)
