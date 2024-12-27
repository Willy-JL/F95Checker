### Note:
- This is a smaller release due to the bugfixes it contains, make sure to also read the changelog for [11.0](https://github.com/Willy-JL/F95Checker/releases/tag/11.0) and [11.0.1](https://github.com/Willy-JL/F95Checker/releases/tag/11.0.1)

### Added:
- ASTC Image Compression option:
  - Compresses images for instantaneous load times (after first compression which is slower)
  - Potentially less VRAM usage, overall slightly less disk usage on average (if ASTC Replace is also enabled, otherwise files are duplicated)
  - Some GPUs may not be compatible, some others may render images less efficiently like this
- Unload Images Off-screen option:
  - Saves a lot of VRAM usage by unloading images not currently shown
  - Only recommended together with ASTC Image Compression, otherwise it is very slow

### Updated:
- More info popup has constant size, easier to read when cycling games as it no longer shifts based on scroll bar being visible or vertical content length (by @Willy-JL)
- Extension > Add in Background now enabled by default for new users (by @Willy-JL)

### Fixed:
- Fixed sorting corruption bug (#211 by @Willy-JL & @FaceCrap)
- Fixed incorrect tab for first frame that caused images from default tab to load (by @Willy-JL)
- Fixed GIF animation speed (by @Willy-JL)
- Shift+Scroll and Shift+Alt+Scroll when zooming banner images scales correctly with FPS and uses smooth scrolling (by @Willy-JL)
- Save new zoom area and times settings after Shift+Scroll and Shift+Alt+Scroll on banner images (by @Willy-JL)
- Optimize some text drawing by using ImGui wrapping instead of slow `wrap_text()` which is now fully gone (by @Willy-JL)
- Slightly improve some hover tooltips, fixed weighted score missing on hover in grid/kanban view (by @Willy-JL)
- Fix flicker when clicking arrows in more info popup (by @Willy-JL)
- Apply images more efficiently, reduce stutters while scrolling (#212 by @Willy-JL)
- Improve images error handling and display (#212 by @Willy-JL)

### Removed:
- Nothing

### Known Issues:
- MacOS webview in frozen binaries remains blank, run from source instead
