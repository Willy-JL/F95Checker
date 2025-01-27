### Added:
- Nothing

### Updated:
- New notification system with buttons and better platform support (#220 by @Willy-JL)
- Updates popup is now cumulative, new updates get grouped with any previous popups and moved to top (#220 by @Willy-JL)

### Fixed:
- Fix switching view modes with "Table header outside list" disabled (by @Willy-JL)
- Fix GUI redraws not pausing when unfocused, hovered and not moving mouse (by @Willy-JL)
- Fix missing libbz2.so on linux binary bundles (#222 by @Willy-JL)

### Removed:
- Excluded `libEGL.so` on linux binary bundles, fixes "Cannot find EGLConfig, returning null config" (by @Willy-JL)

### Known Issues:
- MacOS webview in frozen binaries remains blank, run from source instead
