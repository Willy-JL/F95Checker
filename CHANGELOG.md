### Added:
- Insecure SSL option (by @Willy-JL)
- Archive/Unarchive button to more info popup (by @Willy-JL)
- Allow removing personal rating for selected games in context menu (by @Willy-JL)
- Show full note when hovering notes icon (#198 by @FaceCrap)

### Updated:
- Rename "Last Played" to "Last Launched" and add timeline event when manually setting launched date (by @Willy-JL)
- Save URIs and relative exe path correctly in Launched timeline event (by @Willy-JL)
- Add executable fuzzy matches subdirs in Default Exe Dir for game type, developer, name (by @Willy-JL)
- Add executable checks best partial match to account for versions/mods/other things in dir names (#163 by @MayhemSixx)

### Fixed:
- More efficient grid/kanban cell cluster text (#200 by @Willy-JL)
- Fix Windows start with system setting and quotes usage (#156 by @oneshoekid & @Willy-JL)
- Fix Extension mdi-webfont not loading from RPC (#205 by @FaceCrap)
- Fix Extension context menu missing after browser restart (#206 by @TheOnlyRealKat)
- Redraw screen when DDL is extracting to show when complete (by @Willy-JL)
- Improved Developer name sanitization for some characters like `()[]{}\` (by @Willy-JL)
- Catch font texture exceptions, set texture faster (by @Willy-JL)
- Respect scaling for rounded corners (by @Willy-JL)
- Detect new 502 error code format (by @Willy-JL)

### Removed:
- Removed obsolete DDOS-GUARD bypass, no longer needed and never really worked

### Known Issues:
- Sorting can be sporadically break/change with some actions, seems to be memory corruption inside (py)imgui, re-launch to fix it or change sorting manually
- MacOS webview in frozen binaries remains blank, run from source instead
