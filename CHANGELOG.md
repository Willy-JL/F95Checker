### Added:
- Insecure SSL option (by @Willy-JL)
- Archive/Unarchive button to more info popup (by @Willy-JL)
- Allow removing personal rating for selected games in context menu (by @Willy-JL)
- Show full note when hovering notes icon (#198 by @FaceCrap)

### Updated:
- Rename "Last Played" to "Last Launched" and add timeline event when manually setting launched date (by @Willy-JL)
- Save URIs and relative exe path correctly in Launched timeline event (by @Willy-JL)
- Add executable fuzzy matches subdirs in Default Exe Dir for game type, developer, name (by @Willy-JL)

### Fixed:
- Fix Windows start with system setting and quotes usage (#156 by @oneshoekid & @Willy-JL)
- Fix Extension mdi-webfont not loading from RPC (#205 by @FaceCrap)
- Fix Extension context menu missing after browser restart (#206 by @TheOnlyRealKat)
- Redraw screen when DDL is extracting to show when complete (by @Willy-JL)
- Improved Developer name sanitization for some characters like `()[]{}\` (by @Willy-JL)
- Catch font texture exceptions, set texture faster (by @Willy-JL)
- Respect scaling for rounded corners (by @Willy-JL)

### Removed:
- Nothing

### Known Issues:
- Sorting can be sporadically break/change with some actions, seems to be memory corruption inside (py)imgui, re-launch to fix it or change sorting manually
- MacOS webview in frozen binaries remains blank, run from source instead
