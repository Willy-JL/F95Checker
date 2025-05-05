# https://gist.github.com/WillyJL/82137493896d385a74d148534691b6e1
import os
import pathlib
import string
import sys
import typing

import glfw
import imgui

from modules import (  # added
    callbacks,         # added
    globals,           # added
    icons,             # added
    utils,             # added
)                      # added

dir_icon     = f"{icons.folder_outline}  "         # changed
file_icon    = f"{icons.file_outline}  "           # changed
up_icon      = icons.arrow_up                      # changed
refresh_icon = icons.refresh                       # changed
cancel_icon  = f"{icons.cancel} Cancel"            # changed
open_icon    = f"{icons.folder_open_outline} Open" # changed
ok_icon      = f"{icons.check} Ok"                 # changed


class FilePicker:
    default_flags = (
        imgui.WINDOW_NO_MOVE |
        imgui.WINDOW_NO_RESIZE |
        imgui.WINDOW_NO_COLLAPSE |
        imgui.WINDOW_NO_SAVED_SETTINGS |
        imgui.WINDOW_ALWAYS_AUTO_RESIZE
    )

    __slots__ = (
        "current",
        "title",
        "active",
        "elapsed",
        "buttons",
        "callback",
        "selected",
        "filter_box_text",
        "update_filter",
        "items",
        "dir_picker",
        "dir",
        "flags",
        "windows",
        "drives",
        "current_drive",
    )

    def __init__(
        self,
        title="File picker",
        dir_picker=False,
        start_dir: str | pathlib.Path = None,
        callback: typing.Callable = None,
        buttons: list[str] = [],
        custom_popup_flags=0
    ):
        self.current = 0
        self.title = title
        self.active = True
        self.elapsed = 0.0
        self.buttons = buttons
        self.callback = callback
        self.selected: str = None
        self.filter_box_text = ""
        self.update_filter = False
        self.items: list[str] = []
        self.dir_picker = dir_picker
        self.dir: pathlib.Path = None
        self.flags = custom_popup_flags or self.default_flags
        self.windows = sys.platform.startswith("win")
        if self.windows:
            self.drives: list[str] = []
            self.current_drive = 0
        self.goto(start_dir or os.getcwd())

    def goto(self, dir: str | pathlib.Path):
        dir = pathlib.Path(dir)
        if dir.is_file():
            dir = dir.parent
        if dir.is_dir():
            self.dir = dir
        elif self.dir is None:
            self.dir = pathlib.Path(os.getcwd())
        self.dir = self.dir.absolute()
        self.current = -1
        self.filter_box_text = ""
        self.refresh()

    def refresh(self):
        if self.current != -1:
            selected = self.items[self.current]
        else:
            selected = ""
        self.items.clear()
        try:
            items = list(filter(lambda item: self.filter_box_text.lower() in item.name.lower(), self.dir.iterdir()))
            if len(items) > 0:
                items.sort(key=lambda item: item.name.lower())  # Sort alphabetically
                items.sort(key=lambda item: item.is_dir(), reverse=True)  # Sort dirs first
                for item in items:
                    self.items.append((dir_icon if item.is_dir() else file_icon) + item.name)
            else:
                self.items.append("No items match your filter!" if self.filter_box_text else "This folder is empty!")
        except Exception:
            self.items.append("Cannot open this folder!")
        if self.windows:
            self.drives.clear()
            i = -1
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                try:
                    drive_exists = pathlib.Path(drive).exists()
                except PermissionError:
                    drive_exists = True
                except Exception:
                    drive_exists = False
                if drive_exists:
                    i += 1
                    self.drives.append(drive)
                    if str(self.dir).startswith(drive):
                        self.current_drive = i
        if selected in self.items:
            self.current = self.items.index(selected)
        else:
            self.current = -1

    def tick(self, popup_uuid: str = ""):
        if not self.active:
            return 0, True
        io = imgui.get_io()
        style = imgui.get_style()
        # Auto refresh
        self.elapsed += io.delta_time
        if self.elapsed > 2.0 or self.update_filter:
            self.elapsed = 0.0
            self.refresh()
        # Setup popup
        label = self.title + "###popup_" + popup_uuid  # changed
        if not imgui.is_popup_open(label):
            imgui.open_popup(label)
        closed = False  # added
        opened = 1  # added
        size = io.display_size
        imgui.set_next_window_position(size.x / 2, size.y / 2, pivot_x=0.5, pivot_y=0.5)
        if imgui.begin_popup_modal(label, True, flags=self.flags)[0]:
            imgui.begin_group()
            # Up button
            if imgui.button(up_icon):
                self.goto(self.dir.parent)
            # Drive selector
            if self.windows:
                imgui.same_line()
                imgui.set_next_item_width(imgui.get_font_size() * 4)
                changed, value = imgui.combo("###drive_selector", self.current_drive, self.drives)
                if changed:
                    self.goto(self.drives[value])
            # Location bar
            imgui.same_line()
            imgui.set_next_item_width(size.x * 0.7)
            confirmed, dir = imgui.input_text("###location_bar", str(self.dir), flags=imgui.INPUT_TEXT_ENTER_RETURNS_TRUE)
            if imgui.begin_popup_context_item(f"###location_context"):  # added
                if imgui.selectable(f"{icons.content_copy} Copy", False)[0]:  # added
                    callbacks.clipboard_copy(dir)  # added
                if imgui.selectable(f"{icons.content_paste} Paste", False)[0] and (clip := callbacks.clipboard_paste()):  # added
                    dir = clip  # added
                    confirmed = True  # added
                imgui.end_popup()  # added
            if confirmed:
                self.goto(dir)
            # Refresh button
            imgui.same_line()
            if imgui.button(refresh_icon):
                self.refresh()
            imgui.end_group()
            width = imgui.get_item_rect_size().x

            # Main list
            imgui.set_next_item_width(width)
            imgui.push_style_color(imgui.COLOR_HEADER, *style.colors[imgui.COLOR_BUTTON_HOVERED])  # added
            _, value = imgui.listbox(f"###file_list", self.current, self.items, (size.y * 0.65) / imgui.get_frame_height())
            imgui.pop_style_color()  # added
            if value != -1:
                self.current = min(max(value, 0), len(self.items) - 1)
                item = self.items[self.current]
                is_dir = item.startswith(dir_icon)
                is_file = item.startswith(file_icon)
                if imgui.is_item_hovered() and imgui.is_mouse_double_clicked():
                    if is_dir:
                        self.goto(self.dir / item[len(dir_icon):])
                    elif is_file and not self.dir_picker:
                        self.selected = str(self.dir / item[len(file_icon):])
                        imgui.close_current_popup()
                        closed = True  # added
            else:
                is_dir = True
                is_file = False

            # Cancel button
            if imgui.button(cancel_icon):
                imgui.close_current_popup()
                closed = True
            # Custom buttons
            for button in self.buttons:
                imgui.same_line()
                if imgui.button(button):
                    self.selected = button
                    imgui.close_current_popup()
                    closed = True  # added
            # Open button
            imgui.same_line()
            if value == -1 or not is_dir:
                imgui.internal.push_item_flag(imgui.internal.ITEM_DISABLED, True)
                imgui.push_style_var(imgui.STYLE_ALPHA, style.alpha *  0.5)
            if imgui.button(open_icon):
                self.goto(self.dir / item[len(dir_icon if self.dir_picker else file_icon):])
            if value == -1 or not is_dir:
                imgui.internal.pop_item_flag()
                imgui.pop_style_var()
            # Ok button
            imgui.same_line()
            if not (is_file and not self.dir_picker) and not (is_dir and self.dir_picker):
                imgui.internal.push_item_flag(imgui.internal.ITEM_DISABLED, True)
                imgui.push_style_var(imgui.STYLE_ALPHA, style.alpha *  0.5)
            if imgui.button(ok_icon):
                if value == -1:
                    self.selected = str(self.dir)
                else:
                    self.selected = str(self.dir / item[len(dir_icon if self.dir_picker else file_icon):])
                imgui.close_current_popup()
                closed = True  # added
            if not (is_file and not self.dir_picker) and not (is_dir and self.dir_picker):
                imgui.internal.pop_item_flag()
                imgui.pop_style_var()
            # Selected text
            imgui.same_line()
            prev_pos_x = imgui.get_cursor_pos_x()
            if (is_file and not self.dir_picker) or (is_dir and self.dir_picker):
                if value == -1:
                    imgui.text(f"Selected:  {self.dir.name}")
                else:
                    imgui.text(f"Selected:  {item[len(dir_icon if self.dir_picker else file_icon):]}")
            # Filter bar
            if imgui.is_topmost() and not imgui.is_any_item_active() and (globals.gui.input_chars or any(io.keys_down)):  # added
                if imgui.is_key_pressed(glfw.KEY_BACKSPACE):  # added
                    self.filter_box_text = self.filter_box_text[:-1]  # added
                if globals.gui.input_chars:  # added
                    globals.gui.repeat_chars = True  # added
                imgui.set_keyboard_focus_here()  # added
            imgui.same_line()
            new_pos_x = prev_pos_x + width * 0.5
            imgui.set_cursor_pos_x(new_pos_x)
            imgui.set_next_item_width(width - new_pos_x + 2 * style.item_spacing.x)
            changed, self.filter_box_text = imgui.input_text_with_hint("###filterbar", "Filter...", self.filter_box_text)  # changed
            setter_extra = lambda _=None: setattr(self, "update_filter", True)  # added
            if changed:  # added
                setter_extra()  # added
            if imgui.begin_popup_context_item(f"###filtercontext"):  # added
                utils.text_context(self, "filter_box_text", setter_extra, no_icons=True)  # added
                imgui.end_popup()  # added

            closed = closed or utils.close_weak_popup()  # added
            # imgui.end_popup()  # removed
        else:  # added
            opened = 0  # added
            closed = True  # added
        if closed:  # changed
            if self.callback:
                self.callback(self.selected)
            self.active = False
        return opened, closed  # added


class DirPicker(FilePicker):
    def __init__(
        self,
        title="Directory picker",
        start_dir: str | pathlib.Path = None,
        callback: typing.Callable = None,
        buttons: list[str] = [],
        custom_popup_flags=0
    ):
        super().__init__(
            title=title,
            dir_picker=True,
            start_dir=start_dir,
            callback=callback,
            buttons=buttons,
            custom_popup_flags=custom_popup_flags
        )


# Example usage
if __name__ == "__main__":
    global path
    path = ""
    current_filepicker = None
    while True:  # Your main window draw loop
        with imgui.begin("Example filepicker"):
            imgui.text("Path: " + path)
            if imgui.button("Pick a new file"):
                # Create the filepicker
                def callback(selected):
                    global path
                    path = selected
                current_filepicker = FilePicker("Select a file!", callback=callback)
            if current_filepicker:
                # Draw filepicker every frame
                current_filepicker.tick()
                if not current_filepicker.active:
                    current_filepicker = None
