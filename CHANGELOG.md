### Added:
- ASTC Image Compression option:
  - Compresses images for instantaneous load times (after first compression which is slower)
  - Potentially less VRAM usage, overall slightly less disk usage on average (if ASTC Replace is also enabled, otherwise files are duplicated)
  - Some GPUs may not be compatible, some others may render images less efficiently like this
- Unload Images Off-screen option:
  - Saves a lot of VRAM usage by unloading images not currently shown
  - Only recommended together with ASTC Image Compression, otherwise it is very slow

### Updated:
- Nothing

### Fixed:
- Apply images more efficiently, reduce stutters while scrolling (#212 by @Willy-JL)
- Improve images error handling and display (#212 by @Willy-JL)

### Removed:
- Nothing

### Known Issues:
- MacOS webview in frozen binaries remains blank, run from source instead
