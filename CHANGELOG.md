### Added:
- ASTC Image Compression option (#212 by @Willy-JL):
  - Compresses images for instantaneous load times (after first compression which is slower)
  - Potentially less VRAM usage, overall slightly less disk usage on average (if ASTC Replace is also enabled, otherwise files are duplicated)
  - Some GPUs may not be compatible, some others may render images less efficiently like this
- Unload Images Off-screen option (#212 by @Willy-JL):
  - Saves a lot of VRAM usage by unloading images not currently shown
  - Only recommended together with ASTC Image Compression, otherwise it is very slow
- Play GIFs and Play GIFs Unfocused options (#212 by @Willy-JL):
  - Saves a lot of VRAM if completely disabled, no GIFs play and only first frame is loaded
  - Saves CPU/GPU usage by redrawing less if disabled when unfocused, but still uses same VRAM

### Updated:
- Nothing

### Fixed:
- Fix switching view modes with "Table header outside list" disabled (by @Willy-JL)
- Fix GUI redraws not pausing when unfocused, hovered and not moving mouse (by @Willy-JL)
- Apply images more efficiently, reduce stutters while scrolling (#212 by @Willy-JL)
- Improve images error handling and display (#212 by @Willy-JL)

### Removed:
- Nothing

### Known Issues:
- MacOS webview in frozen binaries remains blank, run from source instead
