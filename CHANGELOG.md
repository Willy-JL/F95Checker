### Added:
- Insecure SSL option (by @Willy-JL)

### Updated:
- Nothing

### Fixed:
- Fix Windows start with system setting and quotes usage (#156 by @oneshoekid & @Willy-JL)
- Redraw screen when DDL is extracting to show when complete (by @Willy-JL)

### Removed:
- Nothing

### Known Issues:
- Sorting can be sporadically break/change with some actions, seems to be memory corruption inside (py)imgui, re-launch to fix it or change sorting manually
- MacOS webview in frozen binaries remains blank, run from source instead
