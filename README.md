# F95Checker
An update checker tool for (NSFW) games on the [F95Zone](https://f95zone.to/) platform

<p align="center">
  <img src=".github/images/F95Checker.png">
</p>

## Features:
 - Insane speed™
 - Beautiful GUI
 - Very easy to setup and use
 - Track what versions you installed and played
 - Launch games straight from the tool
 - Alert and Inbox checker
 - See changelogs
 - See game statuses (completed, on hold, abandoned)
 - Auto Sorting
 - Auto updating
 - Theme support

## Compatibility:
Made with Python 3.8.8 for Windows, has compatibility layer for Linux. If you want this for Mac let me know

## Installation:
The tool comes bundled with both windows EXE and python scripts, so you have two ways to install:

#### Windows EXE:
 - Download below and extract
 - Double-click `F95Checker.exe` when you want to use the tool
#### Python script (Linux):
 - Install Python ( 3.8.8 preferably )from the official [Python website](https://www.python.org/downloads/)
 - Download below and extract
 - Install requirements (`pip install --upgrade -r requirements.txt`)
 - Run "F95Checker.py" with Python (`python3 F95Checker.py`) or use `F95Checker.sh`

## Download:
Versions newer than 7.0 are hosted here on GitHub, in the [releases section](https://github.com/Willy-JL/f95checker/releases)

Older versions are available on the [F95Zone thread](https://f95zone.to/threads/44173/)

## How to use:

#### How to use the GUI:
 - Add games by pasting the game thread link in the input box and clicking "Add"
 - Remove games with the edit mode button on the right
 - Check for updates with the HUGE "Refresh!" button
 - If a game was updated you will get a messagebox telling you
 - Click on a game's name to view it's changelog
 - Open a game by clicking the play button on the left
 - Right click the play button to open the install folder of the game
 - Open a webpage by clicking the "arrow square thingy" on the right
 - Tick the "download" checkbox for games you have installed and then the played checkbox (just left of the installed one) if you played it
 - Change settings on the right under the "Refresh!" button

#### What the settings do:
 - **Open Pages as Saved HTML**: when you open a webpage it will be first downloaded and then opened as an html file; this is useful because it allows you to view links and spoilers without logging in on the browser
 - **Max Retries per Request**: how many times a web request to F95Zone will be retried before failing
 - **Auto Sort**: how the game list will get sorted
 - **BG Refresh Interval (min)**: interval between background mode refreshes in minutes

## How it works:
First of all this script was written in Python 3.8.8, makes use of the aiohttp package to make HTTP requests and runs on the PyQt5 window engine, assisted by qasync to work with asyncio loops.
 - Creates a session to keep cookies alive through search requests.
 - Logs into an account (this is necessary to be able to search for games since links change upon updates).
 - Searches for each game individually with a quicksearch request.
 - Grabs the version from the game title.
 - Compares the version number with the one from the previously saved data.
 - If a game was updated, requests the game thread and identifies the changelog and status.

## Disclaimer:
I know you might be skeptical about inserting your account credentials into some random dude's program, and I totally agree with you if you are, but you can read through the code and if you can understand anything about coding (not even that, python is really similar to english) you will see that this doesn't do anything harmful. If you still aren't sure you can create a second account just for this program.

## Contributing:
Please do! I poured my heart and soul into this tool and hearing suggestions or getting help or pointer with the code really helps!