# https://gist.github.com/Willy-JL/e9e9dac70b7970b6ee12fcf52b9b8f11
import imgui


def ratingwidget(id: str, current: int, num_stars=5, *args, **kwargs):
    value = current
    accent_col = imgui.style.colors[imgui.COLOR_BUTTON_HOVERED]
    imgui.push_style_color(imgui.COLOR_BUTTON, 0, 0, 0, 0)
    imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0, 0, 0, 0)
    imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0, 0, 0, 0)
    imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (0, 0))
    imgui.push_style_var(imgui.STYLE_ITEM_SPACING, (0, 0))
    imgui.push_style_var(imgui.STYLE_FRAME_BORDERSIZE, 0)
    for i in range(1, num_stars + 1):
        if i <= current:
            label = "󰓎"  # Filled / selected star
            imgui.push_style_color(imgui.COLOR_TEXT, *accent_col)
        else:
            label = "󰓒"  # Empty / unselected star
        if imgui.small_button(f"{label}##{id}_{i}", *args, **kwargs):
            value = i if current != i else 0  # Clicking the current value resets the rating to 0
        if i <= current:
            imgui.pop_style_color()
        imgui.same_line()
    value = min(max(value, 0), num_stars)
    imgui.pop_style_color(3)
    imgui.pop_style_var(3)
    imgui.dummy(0, 0)
    return value != current, value


# Example usage
if __name__ == "__main__":
    rating_5 = 0
    rating_10 = 0

    # Note: you will need material design icons or another icon font for this:
    imgui.get_io().fonts.add_font_from_file_ttf(
        "materialdesignicons-webfont.ttf", 16,
        font_config=imgui.core.FontConfig(merge_mode=True),
        glyph_ranges=imgui.core.GlyphRanges([0xf0000, 0xf2000, 0])
    )
    impl.refresh_font_texture()

    while True:  # Your main window draw loop
        with imgui.begin("Example rating"):

            imgui.text("With 5 stars:")
            imgui.same_line()
            changed, rating_5 = ratingwidget("5_stars", rating_5)  # Default star count is 5
            if changed:
                imgui.same_line()
                imgui.text(f"You set me to {rating_5} stars!")

            imgui.text("With 10 stars:")
            imgui.same_line()
            _, rating_10 = ratingwidget("10_stars", rating_10, num_stars=10)
