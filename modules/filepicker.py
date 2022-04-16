import pathlib
import random
import imgui
import os

popup_flags = (
    imgui.WINDOW_NO_MOVE |
    imgui.WINDOW_NO_RESIZE |
    imgui.WINDOW_NO_COLLAPSE
)


class FilePicker:
    def __init__(self, title="File picker", start_dir=None, custom_flags=0):
        self.active = True
        self.selected = None
        self.dir_icon = "󰉋"
        self.file_icon = "󰈔"
        self.current = 0
        self.items = []
        self.dir = None
        self.goto(start_dir or os.getcwd())
        self.id = f"{title}##{str(random.random())[2:]}"
        self.flags = custom_flags or popup_flags
        self.windows = os.name == "nt"
        imgui.open_popup(self.id)

    def goto(self, dir):
        dir = pathlib.Path(dir)
        if dir.is_file():
            dir = dir.parent
        if dir.is_dir():
            self.dir = dir.absolute()
        elif self.dir is None:
            self.dir = pathlib.Path(os.getcwd())
        self.refresh()

    def refresh(self):
        self.items.clear()
        items = list(self.dir.iterdir())
        items.sort(key=lambda item: item.name.lower())
        items.sort(key=lambda item: item.is_dir(), reverse=True)
        for item in items:
            self.items.append((self.dir_icon if item.is_dir() else self.file_icon) + "  " + item.name)

    def tick(self):
        if not self.active:
            return
        # Setup popup
        size = imgui.get_io().display_size
        width = size.x * 0.8
        height = size.y * 0.8
        imgui.set_next_window_size(width, height, imgui.ALWAYS)
        imgui.set_next_window_position(size.x / 2, size.y / 2, pivot_x=0.5, pivot_y=0.5)
        if imgui.begin_popup_modal(self.id, flags=self.flags):

            # Up buttons
            if imgui.button("󰁞"):
                self.goto(self.dir.parent)
            # Location bar
            imgui.same_line()
            imgui.set_next_item_width(-26 - imgui.get_style().item_spacing.x)
            confirmed, dir = imgui.input_text(f"##location_bar_{self.id}", str(self.dir), 9999999, flags=imgui.INPUT_TEXT_ENTER_RETURNS_TRUE)
            if confirmed:
                self.goto(dir)
            # Refresh button
            imgui.same_line()
            if imgui.button("󰑐"):
                self.refresh()

            # Main list
            imgui.begin_child(f"##file_box_{self.id}", border=False, height=-28)
            imgui.set_next_item_width(-0.1)
            clicked, value = imgui.listbox(f"##file_list_{self.id}", self.current, self.items, len(self.items))
            self.current = min(max(value, 0), len(self.items) - 1)
            item = self.items[self.current]
            if clicked:
                if item[0] == self.dir_icon:
                    self.goto(self.dir / item[3:])
            imgui.end_child()

            # Cancel button
            if imgui.button("Cancel"):
                self.selected = ""
                self.active = False
                imgui.close_current_popup()
            # Ok button
            imgui.same_line()
            if item[0] == self.dir_icon:
                imgui.internal.push_item_flag(imgui.internal.ITEM_DISABLED, True)
                imgui.push_style_var(imgui.STYLE_ALPHA, imgui.get_style().alpha *  0.5)
            if imgui.button("Ok"):
                self.selected = str(self.dir / item[3:])
                self.active = False
                imgui.close_current_popup()
            if item[0] == self.dir_icon:
                imgui.internal.pop_item_flag()
                imgui.pop_style_var()
            # Selected text
            if item[0] == self.file_icon:
                imgui.same_line()
                imgui.text(f"Selected:  {item[3:]}")

            imgui.end_popup()
        return self.selected
