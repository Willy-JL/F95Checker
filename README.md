# F95Checker

An update checker and library tool for (NSFW) games on the [F95Zone](https://f95zone.to/) platform.

<p align="center">
  <img src=".github/images/F95Checker.png">
</p>

## Features:

- Blazing fast™ and reliable
- Very easy to setup and use
- Cross platform (windows, linux, macos)
- Beautiful and customizable interface
- Compact list, comfy grid and kanban columns view modes
- 2FA accounts supported
- Alert and inbox checker
- Track what versions you installed and played
- Launch games straight from the tool
- Custom labels, organize your library how you want to
- Archive games to temporarily mute updates
- Supported game details:
  - Name, Version, Developer
  - Type (game engine / type of thread)
  - Status (completed / on hold / abandoned)
  - Last update, last played and added on dates
  - Description / overview and changelog
  - Header images (including gifs)
  - Download links and RPDL.net support
  - Forum tags and personal labels
  - Forum score (value out of 5) and personal rating (5 stars)
  - Personal notes (textbox you can use however you want)
- Sorting and filtering by most of above details, with multisort and multifilter support
- Also supports media (animations, collections...) and normal threads
- Auto updating (the tool, NOT the games)
- Background mode (periodically refresh in background and receive desktop notifications)
- Many ways to add games, including a companion web browser extension

## Compatibility:

Built with Python 3.10+ for Windows, Linux and MacOS.

Binaries are available for all 3 platforms, requiring no setup at all. If instead you want to run from source note that Python 3.10+ is required and you'll need to
install the requirements with pip (development packages might be needed to compile them).

My daily machine runs Arch Linux but I have both Windows and MacOS virtual machines. I always try my best to test the updates on all platforms before release and to
help you when things go wrong, but I can only do so much and with some obscure errors I might not be able to help you.

## Installation:

- **Windows:** Extract and run `F95Checker.exe`

- **Linux:** Extract and run `F95Checker`

- **MacOS:** Extract, right click `F95Checker.app`, select "Open" in the menu and click "Open" in the next popup **\***

- **Source:** Make sure you have Python 3.10+, install requirements with `pip3 install -U -r requirements.txt` and run with `python3 main.py` (this file is marked
executable and has a shebang, you might be able to just double click it!)

**\*** If you get a message saying that the application is damaged and should be moved to the trash you need to: close the popup, open a terminal, navigate to the
location of the `F95Checker.app`, type in `xattr -d com.apple.quarantine F95Checker.app` and press enter; after this the method above to open the app should work fine.

## Download:

Versions after 7.0 are hosted in the [GitHub releases section](https://github.com/Willy-JL/f95checker/releases), while older versions are archived in the
[F95Zone thread](https://f95zone.to/threads/44173/).

### Get the latest release [here](https://github.com/Willy-JL/F95Checker/releases/latest).

## Browser extension

The F95Checker browser addon allows you to easily add games to you desktop F95Checker library while browsing the forum in 3 ways:

- Clicking the extension icon while viewing a thread
- Right clicking a link to a thread
- Right clicking anywhere on the background of a thread page

The extension is available for both major browser families (for example Brave counts as Chrome, LibreWolf counts as Firefox):

- **Chrome:** Open `chrome://extensions/` in browser, enable "Developer mode", reload the page and drag `extension/chrome.zip` (from the tool folder) into the page

- **Firefox:** Install from [AMO](https://addons.mozilla.org/firefox/addon/f95checker-browser-addon/)

Please note that this extension is solely to aid the usage of the desktop tool, you still need the desktop application installed and running.

## FAQ:

- **Crashes on start with GLError 'invalid operation'?**

  Update Windows, update GPU drivers, and if you have them update MSI AfterBurner and RTSS or just disable / remove them.

- **How do I use this tool?** and **How do the versions and checkboxes work?**

  After you have installed it using the instructions above, the day-to-day usage is quite simple. You need to **add the games you want to track** (more on this below)
  and every once in a while you **hit the big `Refresh!` button to check for updates** of your games. Each game has 2 main checkboxes, the `Installed / Downloaded` box
  and the `Played / Finished` box; this should be quite intuitive: if you have a game installed / downloaded on your system, mark it as installed, and once you have
  finished playing the content for that version mark it as played / finished. **When a game receives an update you will get a popup about it at the end of the refresh.**
  If the name changes (the game has been renamed by the developer) or its status changed (e.g. from normal to abandoned) you will get a popup about it. If a version
  number change is detected, however, along with the update popup you will have a few other changes: the played checkbox will be deselected (a new version usually means
  more content is available) and (if you had marked it as installed) the installed checkbox will be half selected. This is because the tool remembers what version you
  had marked as installed, so if a new version is available it will show you that you still have it installed, just not on the latest version. There will also be an
  `Update Available` marker next to the game's name. The version number text will also reflect this, showing both the installed version and the latest version with the
  appropriate icons. In this state you can then click the installed checkbox to mark the latest version as installed.

- **How do I add games to the tool?**

  There are quite a few ways:

  - Open the thread in a browser, copy the URL, paste it in the tool's bottom textbox and click `Add!`
  - Type a name in the bottombar, press enter and select from the options (this uses F95Zone's quicksearch)
  - Using the browser extension (more info above)
  - Using the `Manage > Import` section in the settings sidebar:
    - Thread links to paste multiple links at once
    - F95 bookmarks and watched threads to add the pages you saved on your F95Zone account
    - Browser bookmarks to import the bookmarks you saved in your browser
    - URL shortcut file for Windows web shortcut files

      (For the last 2 you can drag the files into the tool window)

  After adding the games make sure to refresh atleast once to fetch all the game information!

- **Can you make it download game updates?** and **Can you make it detect my game folders?**

  The main reason I decided to make this tool is because all the other alternatives were, in my opinion, too complicated to setup and did way more than what I wanted /
  needed. Most of this overhead I believe comes from trying to manage your game folders and files on disk, which introduces SO much complexity and room for error. That
  is what brought me to making my own program, which will NEVER download updates, manage your folders and so on.
  **F95Checker is not a tool that manages your games, it is a tool that helps you manage your games yourself.**

- **Where is my data stored?**

  F95Checker stores all it's data at:

  - `%APPDATA%\f95checker\` on Windows
    (usually `C:\Users\username\AppData\Roaming\f95checker\`)
  - `~/.config/f95checker/` on Linux
    (usually `/home/username/.config/f95checker/`)
  - `~/Library/Application Support/f95checker/` on MacOS
    (usually `/Users/username/Library/Application Support/f95checker/`)

  in a file named `db.sqlite3`, while images are saved in the `images` folder as `thread-id.ext`. The `imgui.ini` file stores some interface preferences, like window
  size and position, enabled columns and so on. Files named `f95checker.json` and `config.ini` are remainders from previous versions (pre v9.0 and pre v7.0
  respectively). When opening v9.0+ it will attempt to migrate these old configs to the new database system, once that is done these old files will be ignored.

- **How do I customize the interface, the columns and the sorting?**

  Everything to do with columns and sorting can only be changed from list view but also applies to grid and kanban view. Each column has a header bar at the top, you can
  use those o customize the interface. You can drag the headers around to reorder the columns, you can drag the edge of some select columns to change their width (only
  works if other variable size columns are enabled). Left clicking on a header will sort the list by that column, holding shift while clicking a header will add a
  secondary sort (multisort). Right clicking on any header will allow you to enable or disable some columns and also gives you access to manual sort. When manual sort is
  enabled you can drag games (in list and grid mode, not in kanban view) to reorder them. Manual sort remembers the order if you disable and enable it again, but you
  will not be able to reorder the games if you have any filters enabled.

- **How can I try new features early?**

  When I implement new features or work on fixing bugs I submit directly to the [main branch on GitHub](https://github.com/Willy-JL/F95Checker), so running directly from
  the source code there could prove unstable at times, and also requires a development environment with an updated Python install and all the requirements up to date. To
  make testing new versions easier, I sometimes issue beta builds. This usually happens when I make some significant change, or an important bugfix, and want to have
  some binaries that everyone can try easily and give me feedback. **You can see the beta builds in the**
  **[Actions tab on the GitHub repo](https://github.com/Willy-JL/F95Checker/actions);** here you should look for entries with a green tick or a red cross icon. When you
  open one, scroll down to the `Artifacts` section, look for your platform and click on it to download.
  **Keep in mind you will need to be logged into GitHub to download.** If the entry had a red icon, that means that the build has failed for some platforms, but yours
  might be fine so check anyway.

## About the speed™:

F95Zone does not yet have a proper API serving the information needed by this tool, so the only way to gather them is by requesting the full game threads like a normal
browser would. However this is not practical because it consumes a lot of network and computing resources, takes way too long and puts unnecessary stress on the forum
servers. This tool makes a compromise: it makes small HEAD requests to the threads, basically checking if a redirect happens. The URL will usually change when the thread
title is changed, and since many titles contain the version numbers, a redirect will often indicate an update and in that case the full thread will be fetched and
scanned for all the game details. This is what allows F95Checker to quickly check hundreds of games in a matter of seconds. However this will not detect many other
changes, like status and description, so the tool will run periodic full rechecks once a week. When a full recheck happens you will see the status text in the bottom
right corner saying "Running x full rechecks".

## Progress and plans tracker:

Upcoming features and fixes are tracked on the [GitHub Project page](https://github.com/users/Willy-JL/projects/2/views/1).

You can pitch your feature requests and bug reports either in the [GitHub issues](https://github.com/Willy-JL/F95Checker/issues) or on the
[F95Zone thread](https://f95zone.to/threads/44173/).

## Disclaimer:

Due to the lack of a proper F95Zone API, this tool needs to grab the threads just like a browser would, and this entails requiring an account to read spoiler content. I
know you might be skeptical about inserting your account credentials into some random dude's program, and I totally agree with you if you are, but you can read through
the code and you will see that this doesn't do anything harmful. If you still aren't sure you can create a second account just for this program.

## Contributing:

Please do! I poured my heart and soul into this tool and hearing suggestions or getting help with the code really helps!

You can help out in many ways, from simply suggesting features or reporting bugs (you can do those in the [GitHub issues](https://github.com/Willy-JL/F95Checker/issues)
or on the [F95Zone thread](https://f95zone.to/threads/44173/)), to adding to the codebase (through [GitHub pull requests](https://github.com/Willy-JL/F95Checker/pulls)
or by posting patches in the [F95Zone thread](https://f95zone.to/threads/44173/)).

## Developer note:

This software is licensed under the 3rd revision of the GNU General Public License (GPLv3) and is provided to you for free. Furthermore, due to its license, it is also
free as in freedom: you are free to use, study, modify and share this software in whatever way you wish as long as you keep the same license.

However, F95Checker is actively developed by one person only, WillyJL, and not with the aim of profit but out of personal interest and benefit for the whole F95Zone
community. Donations are although greatly appreciated and aid the development of this software. You can find donation links [here](https://linktr.ee/WillyJL).

If you find bugs or have some feedback, don't be afraid to let me know either on GitHub (using issues or pull requests) or on F95Zone (in the thread comments or in
direct messages).

Please note that this software is not ( yet ;) ) officially affiliated with the F95Zone platform.

## Cool people:

Supporters:

[FaceCrap](https://f95zone.to/members/2913051/) - [ascsd](https://f95zone.to/members/3977760/) - [Jarulf](https://f95zone.to/members/2709937/) -
[rozzic](https://f95zone.to/members/449099/) - [warez_gamez](https://f95zone.to/members/81517/) - [DarkVermilion](https://f95zone.to/members/4392187/) - And 1 anon

Contributors:

- [GR3ee3N](https://github.com/GR3ee3N): Optimized build workflows and other PRs
- [batblue](https://f95zone.to/members/4143766/): MacOS suppport and feedback guy
- [unroot](https://f95zone.to/members/1585550/): Linux support and feedback guy
- [ploper26](https://f95zone.to/members/1295524/): Suggested HEAD requests for refreshing
- [ascsd](https://f95zone.to/members/3977760/): Helped with brainstorming on some issues and gave some tips
- [blackop](https://f95zone.to/members/4831191/): Helped fix some login window issues on Linux

Community:

[abada25](https://f95zone.to/members/1679118/) - [AtotehZ](https://f95zone.to/members/840616/) - [bitogno](https://f95zone.to/members/605466/) -
[d_pedestrian](https://f95zone.to/members/2616862/) - [DarK x Duke](https://f95zone.to/members/1852502/) - [GrammerCop](https://f95zone.to/members/2114990/) -
[MillenniumEarl](https://f95zone.to/members/1470797/) - [SmurfyBlue](https://f95zone.to/members/671/) - [yohudood](https://f95zone.to/members/26049/) -
And others that I might be forgetting
