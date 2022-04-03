from modules import globals
import aiosqlite
import asyncio

connection: aiosqlite.Connection = None
available: bool = False
pending: int = 0


async def _wait_connection():
    while not available:
        await asyncio.sleep(0.25)


async def wait_connection():
    await asyncio.wait_for(_wait_connection(), timeout=30)


async def _wait_pending():
    while pending > 0:
        await asyncio.sleep(0.25)


async def wait_pending():
    await asyncio.wait_for(_wait_pending(), timeout=30)


async def connect():
    global available, connection
    connection = await aiosqlite.connect(globals.data_path / "db.sqlite3")
    available = True


# Committing should save to disk, but for some reason it only does so after closing
async def save_to_disk():
    global available
    available = False
    await wait_pending()
    await connection.commit()
    await connection.close()
    await connect()


async def execute(request, *args):
    global pending
    await wait_connection()
    pending += 1
    try:
        await connection.execute(request, *args)
    finally:
        pending -= 1
