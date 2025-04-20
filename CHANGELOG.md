### Added:
- Reviews Tab in More Info Popup (#224 by @Willy-JL)
  - Labels moved next to executables
- Image Texture Compression (`(ASTC or BC7) + ZSTD`) option (#212 by @Willy-JL):
  - Compresses images for instantaneous load times (after first compression which is slower)
  - Less VRAM usage, and potentially less disk usage, depending on configuration and GPU support
  - Check the hover info in settings section for details on trade-offs
- Unload Images Off-screen option (#212 by @Willy-JL):
  - Saves a lot of VRAM usage by unloading images not currently shown
  - Works best together with Tex Compress, so image load times are less noticeable
- Preload Nearby Images option (by @Willy-JL):
  - Starts loading images that aren't visible yet but are less than a window width/height scroll away
  - Works best together with Tex Compress, so image load times are completely unnoticeable
- Play GIFs and Play GIFs Unfocused options (#212 by @Willy-JL):
  - Saves a lot of VRAM if completely disabled, no GIFs play and only first frame is loaded
  - Saves CPU/GPU usage by redrawing less if disabled when unfocused, but still uses same VRAM
- Tabs can now be reordered by dragging (by @Willy-JL)

### Updated:
- New notification system with buttons and better platform support, option to include banner image in update notifs (#220 by @Willy-JL)
- Updates popup is now cumulative, new updates get grouped with any previous popups and moved to top (#220 by @Willy-JL)
- Executable paths in More Info popup wrap after `/` and `\` characters for easier readability (by @Willy-JL)

### Fixed:
- Fix switching view modes with "Table header outside list" disabled (by @Willy-JL)
- Fix flashbang while interface is loading (#221 by @sodamouse)
- Fix GUI redraws not pausing when unfocused, hovered and not moving mouse (by @Willy-JL)
- Fix missing `libbz2.so` on linux binary bundles (#222 by @Willy-JL)
- Apply images more efficiently, eliminate stutters while scrolling, start showing GIFs before all frames are loaded (by @Willy-JL)
- Improve images error handling and display (#212 by @Willy-JL)
- Tags now sort alphabetically as expected (by @Willy-JL)
- UTF-8 encoding is now forced (#230 by @Willy-JL)

### Removed:
- Excluded `libEGL.so` on linux binary bundles, fixes "Cannot find EGLConfig, returning null config" (by @Willy-JL)

### Known Issues:
- MacOS webview in frozen binaries remains blank, run from source instead
