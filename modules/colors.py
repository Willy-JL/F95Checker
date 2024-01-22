import functools


@functools.cache
def hex_to_rgba_0_1(hex: str):
    r = int(hex[1:3], base=16) / 255
    g = int(hex[3:5], base=16) / 255
    b = int(hex[5:7], base=16) / 255
    if len(hex) > 7:
        a = int(hex[7:9], base=16) / 255
    else:
        a = 1.0
    return (r, g, b, a)


@functools.cache
def rgba_0_1_to_hex(rgba: tuple[int, int, int, int | None]):
    r = "%.2x" % int(rgba[0] * 255)
    g = "%.2x" % int(rgba[1] * 255)
    b = "%.2x" % int(rgba[2] * 255)
    if len(rgba) > 3:
        a = "%.2x" % int(rgba[3] * 255)
    else:
        a = "FF"
    return f"#{r}{g}{b}{a}"


# credit: https://stackoverflow.com/a/1855903
@functools.cache
def foreground_color(bg: tuple[int, int, int, int | None]):
    # calculcates 'perceptive luminance'
    luma = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
    return (0.0, 0.0, 0.0, 1.0) if luma > 0.5 else (1.0, 1.0, 1.0, 1.0)
