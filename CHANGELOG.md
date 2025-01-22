### Added:
- Nothing

### Updated:
- DDL can extract 7zip and RAR archives too (by @Willy-JL)
- App icons are now rounded, and MacOS icon has an empty border to fit design guidelines (by @rakleed & @Willy-JL)

### Fixed:
- DDL files are deleted asynchronously now, avoids stutters on slow drives (by @Willy-JL)
- Simplify some error handling, correctly handles connection issues in some edge cases (by @Willy-JL)
- Fix some link icons not being recognized by the extension and missing the library icon (by @Willy-JL)
- Detect system SSL certificates on more Linux distros, include certifi as fallback (by @kalvisbuls & @Willy-JL)

### Removed:
- Nothing

### Known Issues:
- MacOS webview in frozen binaries remains blank, run from source instead
