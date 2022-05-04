from PIL import Image, ImageSequence
import OpenGL.GL as gl
import pathlib
import typing
import imgui
import numpy
import glfw
import sys
import os

from modules import sync_thread


# Utils

def impl_glfw_init(width: int, height: int, window_name: str):
    # FIXME: takes quite a while to initialize on my arch linux machine
    if not glfw.init():
        print("Could not initialize OpenGL context")
        sys.exit(1)

    # OS X supports only forward-compatible core profiles from 3.2
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)

    # Create a windowed mode window and its OpenGL context
    window = glfw.create_window(width, height, window_name, None, None)
    glfw.make_context_current(window)

    if not window:
        glfw.terminate()
        print("Could not initialize Window")
        sys.exit(1)

    return window


def push_disabled(block_interaction: bool = True):
    if block_interaction:
        imgui.internal.push_item_flag(imgui.internal.ITEM_DISABLED, True)
    imgui.push_style_var(imgui.STYLE_ALPHA, imgui.style.alpha *  0.5)


def pop_disabled(block_interaction: bool = True):
    if block_interaction:
        imgui.internal.pop_item_flag()
    imgui.pop_style_var()


def center_next_window():
    size = imgui.io.display_size
    imgui.set_next_window_position(size.x / 2, size.y / 2, pivot_x=0.5, pivot_y=0.5)


def close_popup_clicking_outside():
    if not imgui.is_popup_open("", imgui.POPUP_ANY_POPUP_ID):
        # This is the topmost popup
        if imgui.is_mouse_clicked():
            # Mouse was just clicked
            pos = imgui.get_window_position()
            size = imgui.get_window_size()
            if not imgui.is_mouse_hovering_rect(pos.x, pos.y, pos.x + size.x, pos.y + size.y, clip=False):
                # Popup is not hovered
                imgui.close_current_popup()
                return True
    return False


# Widgets

class ImGuiImage:
    def __init__(self, path: str | pathlib.Path, glob: str = ""):
        self.width: int = 1
        self.height: int = 1
        self.glob: str = glob
        self.frame_count: int = 1
        self.loaded: bool = False
        self.loading: bool = False
        self.applied: bool = False
        self.missing: bool = False
        self.animated: bool = False
        self.prev_time: float = 0.0
        self.current_frame: int = -1
        self.frame_elapsed: float = 0.0
        self.frame_durations: list = None
        self.data: bytes | list[bytes] = None
        self._texture_id: numpy.uint32 = None
        self.path = pathlib.Path(path)

    def reset(self):
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture_id)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, 0, 0, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, b"\x00\x00\x00\xff")
        self.applied = False

    @staticmethod
    def get_rgba_pixels(image: Image.Image):
        if image.mode == "RGB":
            return image.tobytes("raw", "RGBX")
        else:
            if image.mode != "RGBA":
                image = image.convert("RGBA")
            return image.tobytes("raw", "RGBA")

    def set_missing(self):
        self.missing = True
        self.loaded = True
        self.loading = False

    def reload(self):
        path = self.path
        if self.glob:
            paths = list(path.glob(self.glob))
            if not paths:
                self.set_missing()
                return
            paths.sort(key=lambda path: path.suffix != ".gif")
            path = paths[0]
        if path.is_file():
            self.missing = False
        else:
            self.set_missing()
            return
        image = Image.open(path)
        self.width, self.height = image.size
        if hasattr(image, "n_frames") and image.n_frames > 1:
            self.animated = True
            self.data = []
            self.frame_durations = []
            for frame in ImageSequence.Iterator(image):
                self.data.append(self.get_rgba_pixels(frame))
                self.frame_durations.append(frame.info["duration"] / 1250)
            self.frame_count = len(self.data)
        else:
            self.data = self.get_rgba_pixels(image)
        self.loaded = True
        self.loading = False

    def apply(self, data: bytes):
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, self.width, self.height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)

    @property
    def texture_id(self):
        if self._texture_id is None:
            self._texture_id = gl.glGenTextures(1)
        if not self.loaded:
            if not self.loading:
                self.loading = True
                self.reset()
                sync_thread.queue(self.reload)
        elif not self.missing:
            if self.animated:
                if self.prev_time != (new_time := imgui.get_time()):
                    self.prev_time = new_time
                    self.frame_elapsed += imgui.io.delta_time
                if self.frame_elapsed > self.frame_durations[max(self.current_frame, 0)]:
                    self.frame_elapsed = 0
                    self.applied = False
                if not self.applied:
                    self.current_frame += 1
                    if self.current_frame == self.frame_count:
                        self.current_frame = 0
                    self.apply(self.data[self.current_frame])
                    self.applied = True
            elif not self.applied:
                self.apply(self.data)
                self.applied = True
        return self._texture_id

    def render(self, width: int, height: int, *args, **kwargs):
        if self.missing:
            return
        if imgui.is_rect_visible(width, height):
            if "rounding" in kwargs:
                flags = kwargs.pop("flags", None)
                if flags is None:
                    flags = imgui.DRAW_ROUND_CORNERS_ALL
                pos = imgui.get_cursor_screen_pos()
                pos2 = (pos.x + width, pos.y + height)
                draw_list = imgui.get_window_draw_list()
                draw_list.add_image_rounded(self.texture_id, tuple(pos), pos2, *args, flags=flags, **kwargs)
                imgui.dummy(width, height)
            else:
                imgui.image(self.texture_id, width, height, *args, **kwargs)
        else:
            # Skip if outside view
            imgui.dummy(width, height)

    def crop_to_ratio(self, ratio: int | float, fit: bool = False):
        img_ratio = self.width / self.height
        if (img_ratio >= ratio) != fit:
            crop_h = self.height
            crop_w = crop_h * ratio
            crop_x = (self.width - crop_w) / 2
            crop_y = 0
            left = crop_x / self.width
            top = 0
            right = (crop_x + crop_w) / self.width
            bottom = 1
        else:
            crop_w = self.width
            crop_h = crop_w / ratio
            crop_y = (self.height - crop_h) / 2
            crop_x = 0
            left = 0
            top = crop_y / self.height
            right = 1
            bottom = (crop_y + crop_h) / self.height
        return (left, top), (right, bottom)


class FilePicker:
    flags = (
        imgui.WINDOW_NO_MOVE |
        imgui.WINDOW_NO_RESIZE |
        imgui.WINDOW_NO_COLLAPSE |
        imgui.WINDOW_NO_SAVED_SETTINGS |
        imgui.WINDOW_ALWAYS_AUTO_RESIZE
    )

    def __init__(self, title: str = "File picker", start_dir: str | pathlib.Path = None, callback: typing.Callable = None, custom_flags: int = 0):
        self.current: int = 0
        self.title: str = title
        self.active: bool = True
        self.dir_icon: str = "󰉋"
        self.file_icon: str = "󰈔"
        self.elapsed: float = 0.0
        self.selected: str = None
        self.items: list[str] = []
        self.dir: pathlib.Path = None
        self.callback: typing.Callable = callback
        self.flags: int = custom_flags or self.flags
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
        self.refresh()

    def refresh(self):
        if self.current != -1:
            selected = self.items[self.current]
        else:
            selected = ""
        self.items.clear()
        try:
            items = list(self.dir.iterdir())
            if len(items) > 0:
                items.sort(key=lambda item: item.name.lower())
                items.sort(key=lambda item: item.is_dir(), reverse=True)
                for item in items:
                    self.items.append((self.dir_icon if item.is_dir() else self.file_icon) + "  " + item.name)
            else:
                self.items.append("This folder is empty!")
        except Exception:
            self.items.append("Cannot open this folder!")
        if selected in self.items:
            self.current = self.items.index(selected)
        else:
            self.current = -1

    def draw(self):
        if not self.active:
            return
        # Auto refresh
        self.elapsed += imgui.io.delta_time
        if self.elapsed > 2:
            self.elapsed = 0.0
            self.refresh()
        # Setup popup
        if not imgui.is_popup_open(self.title):
            imgui.open_popup(self.title)
        center_next_window()
        if imgui.begin_popup_modal(self.title, True, flags=self.flags)[0]:
            close_popup_clicking_outside()
            size = imgui.io.display_size

            imgui.begin_group()
            # Up buttons
            if imgui.button("󰁞"):
                self.goto(self.dir.parent)
            # Location bar
            imgui.same_line()
            imgui.set_next_item_width(size.x * 0.7)
            confirmed, dir = imgui.input_text("##location_bar", str(self.dir), 9999999, flags=imgui.INPUT_TEXT_ENTER_RETURNS_TRUE)
            if confirmed:
                self.goto(dir)
            # Refresh button
            imgui.same_line()
            if imgui.button("󰑐"):
                self.refresh()
            imgui.end_group()
            width = imgui.get_item_rect_size().x

            # Main list
            imgui.set_next_item_width(width)
            clicked, value = imgui.listbox(f"##file_list", self.current, self.items, (size.y * 0.65) / imgui.get_frame_height())
            if value != -1:
                self.current = min(max(value, 0), len(self.items) - 1)
                item = self.items[self.current]
                is_dir = item[0] == self.dir_icon
                is_file = item[0] == self.file_icon
                if imgui.is_item_hovered() and imgui.is_mouse_double_clicked():
                    if is_dir:
                        self.goto(self.dir / item[3:])
                    elif is_file:
                        self.selected = str(self.dir / item[3:])
                        imgui.close_current_popup()
            else:
                is_dir = False
                is_file = False

            # Cancel button
            if imgui.button("󰜺 Cancel"):
                imgui.close_current_popup()
            # Ok button
            imgui.same_line()
            if not is_file:
                push_disabled()
            if imgui.button("󰄬 Ok"):
                self.selected = str(self.dir / item[3:])
                imgui.close_current_popup()
            if not is_file:
                pop_disabled()
            # Selected text
            if is_file:
                imgui.same_line()
                imgui.text(f"Selected:  {item[3:]}")

            imgui.end_popup()
        if not imgui.is_popup_open(self.title):
            if self.callback:
                self.callback(self.selected)
            self.active = False
