# F95Checker

An update checker and library tool for (NSFW) games on the [F95zone](https://f95zone.to/) platform.

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
  - Last update, last launched and added on dates
  - Description / overview and changelog
  - Header images (including gifs)
  - Download links, F95zone Donor DDL and RPDL.net support
  - Forum tags and personal labels
  - Forum score (value out of 5) and personal rating (5 stars)
  - Personal notes (textbox you can use however you want)
- Sorting and filtering by most of above details, with multisort and multifilter support
- Also supports media (animations, collections...) and normal threads
- Custom games to manually add games from other platforms
- Auto updating (the tool, NOT the games)
- Background mode (periodically refresh in background and receive desktop notifications)
- Many ways to add games, including a companion web browser extension

## Download: [here](https://github.com/Willy-JL/F95Checker/releases/latest)

## Compatibility:

Built with Python 3.11+ for Windows, Linux and MacOS.

Binaries are available for all 3 platforms, requiring no setup at all. If instead you want to run from source note that Python 3.11+ is required and you'll need to
install the requirements with pip.

## Installation:

- **Windows:** Extract and run `F95Checker.exe`

- **Linux:** Extract and run `F95Checker`

- **MacOS:** Extract, right click `F95Checker.app`, select "Open" in the menu and click "Open" in the next popup **\***

- **Source:** Make sure you have Python 3.11+, install requirements with `pip3 install -U -r requirements.txt` and run with `python3 main.py` (this file is marked
executable and has a shebang, you might be able to just double click it!)

**\*** If MacOS says the application is damaged and should be moved to the trash you need to: close the popup, open a terminal, navigate to the
location of the `F95Checker.app`, type in `xattr -d com.apple.quarantine F95Checker.app` and press enter; after this the method above to open the app should work fine.

## Browser extension

The F95Checker browser addon allows you to easily add games to you desktop F95Checker library while browsing the forum in 3 ways:

- Clicking the extension icon while viewing a thread
- Right clicking a link to a thread
- Right clicking anywhere on the background of a thread page

Also, it allows you to quickly see what games you have added to your list (and which tab) with convenient icons on the forum.

The extension is available for both major browser families (Brave and Edge count as Chrome, LibreWolf counts as Firefox):

- **Chrome:** Open `chrome://extensions/` in browser, enable "Developer mode", reload the page and drag `browser/chrome.zip` (from the tool folder) into the page

- **Firefox:** Install from [AMO](https://addons.mozilla.org/firefox/addon/f95checker-browser-addon/)

Alternatively, you can find a guided install in F95Checker sidebar, in Extension > Install.

Please note that this extension is solely to aid the usage of the desktop tool, you still need the desktop application installed and running.

## FAQ:

- **Crashes on start with GLError 'invalid operation'?**

  Update Windows, update GPU drivers, and if you have them update MSI AfterBurner and RTSS or just disable / remove them.

- **How do I use this tool?** and **How do the versions and checkboxes work?**

  After you have installed it using the instructions above, the day-to-day usage is quite simple. You need to **add the games you want to track** (more on this below)
  and every once in a while you **hit the big `Refresh!` button to check for updates** of your games. Each game has 2 main checkboxes, the `Installed` checkbox
  and the `Finished` checkbox; this should be quite intuitive: if you have a game downloaded on your system, mark it as installed, and once you have finished
  playing the content for that version mark it as finished. **When a game receives an update you will get a popup about it at the end of the refresh.**
  If the name changes (the game has been renamed by the developer) or its status changed (e.g. from normal to abandoned) you will get a popup about it. If a version
  number change is detected, however, along with the update popup there will also be an `Update Available` marker next to the game's name and the installed checkbox
  will be half selected. This is because the tool remembers what version you had marked as installed, so it will show you that you still have it installed, just not
  on the latest version. The finished checkbox will still be selected, because you had finished that installed version. In this state you can click the installed
  checkbox to mark the latest version as installed. Now the finished checkbox will be half selected instead, because the version that is now installed is not what
  you had marked as finished, indicating that there is now more content you haven't played yet.
  **Essentially, remember that the `Installed` box means `Do I have the latest version downloaded?`, and the `Finished` box means `Did I finish playing what I have downloaded?`**

- **How do I add games to the tool?**

  There are quite a few ways:

  - Open the thread in a browser, copy the URL, paste it in the tool's bottom textbox and click `Add!`
  - Type a name in the bottombar, press enter and select from the options (this uses F95zone's latest updates search)
  - Using the browser extension (more info above)
  - Using the `Manage > Import` section in the settings sidebar:
    - Thread links to paste multiple links at once
    - F95zone bookmarks and watched threads to add the pages you saved on your F95zone account
    - Browser bookmarks to import the bookmarks you saved in your browser
    - URL shortcut file for Windows web shortcut files

      (For the last 2 you can drag the files into the tool window)

  After adding the games make sure to refresh atleast once to fetch all the game information!

- **Can you make it download game updates?** and **Can you make it detect my game folders?**

  The main reason I decided to make this tool is because all the other alternatives were, in my opinion, too complicated to setup and did way more than what I wanted /
  needed. Most of this overhead I believe comes from trying to manage your game folders and files on disk, which introduces SO much complexity and room for error. That
  is what brought me to making my own program, which will not automatically download updates, manage your folders and so on.
  **F95Checker is not a tool that manages your games, it is a tool that helps you manage your games yourself.**
  Downloads are supported with normal download links, F95zone Donor DDL and RPDL.net torrents, but starting the downloads and moving files are for you to manage.

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
  use those to customize the interface. You can drag the headers around to reorder the columns, you can drag the edge of some select columns to change their width (only
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

  Have a look at this [visual guide](https://f95zone.to/threads/f95checker-willyjl.44173/post-15396547) if you still have doubts.

## About the speed™:

F95zone does not yet have a proper API serving the information needed by this tool, so the only way to gather them is by requesting the full game threads like a normal
browser would. However this is not practical because it consumes a lot of network and computing resources, takes way too long and puts unnecessary stress on the forum
servers.

This project makes a compromise: I run an independent cache API `api.f95checker.dev` (internally called F95Indexer) specifically for this tool, which will request
the threads from F95zone when someone refreshes them from F95Checker, parse them for relevant data and then cache this data. When you refresh, you only get data from this
dedicated API, not directly from F95zone. This data is cached for up to 7 days, with some exceptions:
- it monitors F95zone Latest Updates every 5 minutes, most updates are detected within this time frame
- all version numbers tracked by F95zone Latest Updates are checked every 12 hours, this detects unpromoted updates
- threads not tracked by F95zone Latest Updates at all are checked at least every 2 days
- other thread types and other changes not in F95zone Latest Updates are checked at least every 7 days
- if a requested thread does not exist, it will not be checked again for 14 days

The tool will ask this API when the last time was that a thread changed any of its data, 10 threads at a time; the API will check if any of these are due to be
checked again, do it if so, then return the timestamps; the tool will only fetch the full data for threads that changed since the last refresh (unless you force a
full refresh, in which case the full data for all threads is fetched).

This is what allows F95Checker to quickly check thousands of games in a matter of seconds. However running a full recheck on your end will not force the cache API to
get new data, so when some less important details change they will be detected at most 7 days later.

## Progress and plans tracker:

Upcoming features and fixes are tracked on the [GitHub Project page](https://github.com/users/Willy-JL/projects/2/views/1).

You can pitch your feature requests and bug reports either in the [GitHub issues](https://github.com/Willy-JL/F95Checker/issues) or on the
[F95zone thread](https://f95zone.to/threads/44173/).

## Old versions:

Versions before 7.0 are archived in the [F95zone thread](https://f95zone.to/threads/44173/).

## Disclaimer:

As of F95Checker 11.0, you can use the tool without logging into F95zone. Some actions still require an account however:
- Download links and F95zone Donor DDL (RPDL.net torrents require their own separate account)
- Alerts and inbox notification checking (disabled by default as of 11.0)
- Importing bookmarked and watched threads
- Opening webpages if you enabled Browser > Download pages (otherwise images and spoiler content would be broken)
I know you might be skeptical about inserting your account credentials into some random dude's program, and I totally agree with you if you are, but you can read through
the code and you will see that this doesn't do anything harmful. If you still aren't sure you can create a second account just for this program.

## Contributing:

Please do! I poured my heart and soul into this tool and hearing suggestions or getting help with the code really helps!

You can help out in many ways, from simply suggesting features or reporting bugs (you can do those in the [GitHub issues](https://github.com/Willy-JL/F95Checker/issues)
or on the [F95zone thread](https://f95zone.to/threads/44173/)), to adding to the codebase (through [GitHub pull requests](https://github.com/Willy-JL/F95Checker/pulls)
or by posting patches in the [F95zone thread](https://f95zone.to/threads/44173/)).

## Developer note:

This software is licensed under the 3rd revision of the GNU General Public License (GPLv3) and is provided to you for free. Furthermore, due to its license, it is also
free as in freedom: you are free to use, study, modify and share this software in whatever way you wish as long as you keep the same license.

However, F95Checker is actively developed by one person only, WillyJL, and not with the aim of profit but out of personal interest and benefit for the whole F95zone
community. Donations are although greatly appreciated and aid the development of this software. You can find donation links [here](https://linktr.ee/WillyJL).

If you find bugs or have some feedback, don't be afraid to let me know either on GitHub (using issues or pull requests) or on F95zone (in the thread comments or in
direct messages).

Please note that this software is not ( yet ;) ) officially affiliated with the F95zone platform.

## Cool people:

Supporters:

[FaceCrap](https://f95zone.to/members/2913051/) - [WhiteVanDaycare](https://f95zone.to/members/3509231/) - [ascsd](https://f95zone.to/members/3977760/) -
[Jarulf](https://f95zone.to/members/2709937/) - [rozzic](https://f95zone.to/members/449099/) - [Belfaier](https://f95zone.to/members/7363156/) -
[warez_gamez](https://f95zone.to/members/81517/) - [DeadMoan](https://f95zone.to/members/4392187/) - And 3 anons

Contributors:

- [r37r05p3C7](https://github.com/r37r05p3C7): Tab idea and customization, timeline, many extension features
- [littleraisins](https://github.com/littleraisins): Fixes, features and misc ideas from the (defunct) 'X' fork
- [FaceCrap](https://github.com/FaceCrap): Multiple small fixes, improvements and finetuning
- [blackop](https://github.com/disaster2395): Proxy support, temporary ratelimit fix, linux login fix
- [Sam](https://f95zone.to/members/7899/): Support from F95zone side to make much this possible
- [GR3ee3N](https://github.com/GR3ee3N): Optimized build workflows and other PRs
- [batblue](https://f95zone.to/members/4143766/): MacOS suppport and feedback guy
- [unroot](https://f95zone.to/members/1585550/): Linux support and feedback guy
- [ploper26](https://f95zone.to/members/1295524/): Suggested HEAD requests for refreshing
- [ascsd](https://f95zone.to/members/3977760/): Helped with brainstorming on some issues and gave some tips

Community:

[abada25](https://f95zone.to/members/1679118/) - [AtotehZ](https://f95zone.to/members/840616/) - [bitogno](https://f95zone.to/members/605466/) -
[BrockLanders](https://f95zone.to/members/2707184/) -
[d_pedestrian](https://f95zone.to/members/2616862/) -
[Danv](https://f95zone.to/members/2758580/) - [DarK x Duke](https://f95zone.to/members/1852502/) - [Dukez](https://f95zone.to/members/3182770/) - [GrammerCop](https://f95zone.to/members/2114990/) - [harem.king](https://f95zone.to/members/6410446/) -
[MillenniumEarl](https://f95zone.to/members/1470797/) - [simple_human](https://f95zone.to/members/1056502/) - [SmurfyBlue](https://f95zone.to/members/671/) - [WhiteVanDaycare](https://f95zone.to/members/3509231/) - [yohudood](https://f95zone.to/members/26049/) -
And others that I might be forgetting
