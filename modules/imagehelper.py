# https://gist.github.com/Willy-JL/9c5116e5a11abd559c56f23aa1270de9
from PIL import Image, ImageSequence, UnidentifiedImageError
import OpenGL.GL as gl
import functools
import pathlib
import imgui

from modules import (  # added
    sync_thread,       # added
)                      # added

redraw = False  # added
_dummy_texture_id = None


def dummy_texture_id():
    global _dummy_texture_id
    if _dummy_texture_id is None:
        _dummy_texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, _dummy_texture_id)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, 0, 0, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, b"\x00\x00\x00\xff")
    return _dummy_texture_id


def get_rgba_pixels(image: Image.Image):
    if image.mode == "RGB":
        return image.tobytes("raw", "RGBX")
    else:
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        return image.tobytes("raw", "RGBA")


@functools.cache
def _crop_to_ratio(width, height, ratio: int | float, fit=False):
    img_ratio = width / height
    if (img_ratio >= ratio) != fit:
        crop_h = height
        crop_w = crop_h * ratio
        crop_x = (width - crop_w) / 2
        crop_y = 0
        left = crop_x / width
        top = 0
        right = (crop_x + crop_w) / width
        bottom = 1
    else:
        crop_w = width
        crop_h = crop_w / ratio
        crop_y = (height - crop_h) / 2
        crop_x = 0
        left = 0
        top = crop_y / height
        right = 1
        bottom = (crop_y + crop_h) / height
    return (left, top), (right, bottom)


class ImageHelper:
    def __init__(self, path: str | pathlib.Path, glob=""):
        self.width = 1
        self.height = 1
        self.frame = -1
        self.glob = glob
        self.elapsed = 0.0
        self.loaded = False
        self.loading = False
        self.applied = False
        self.missing = False
        self.invalid = False
        self.prev_time = 0.0
        self.animated = False
        self.frames: list[bytes] = []
        self.durations: list[float] = []
        self.texture_ids: list[int] = []
        self.resolved_path: pathlib.Path = None
        self.path: pathlib.Path = pathlib.Path(path)
        self.resolve()

    def resolve(self):
        self.resolved_path = self.path
        if self.glob:
            paths = list(self.resolved_path.glob(self.glob))
            if not paths:
                self.missing = True
                return
            # If you want you can setup preferred extensions like this:
            paths.sort(key=lambda path: path.suffix != ".gif")  # changed
            # This will prefer .gif files!
            self.resolved_path = paths[0]
        self.missing = not self.resolved_path.is_file()

    def reload(self):
        self.loaded = False
        self.loading = True
        self.applied = False
        self.resolve()

        self.frame = -1
        self.elapsed = 0.0
        self.frames.clear()
        self.invalid = False
        self.animated = False
        self.durations.clear()
        self.width, self.height = (1, 1)

        if self.missing:
            self.loaded = True
            self.loading = False
            return

        try:
            image = Image.open(self.resolved_path)
        except UnidentifiedImageError:
            self.invalid = True
            self.loaded = True
            self.loading = False
            return

        self.width, self.height = image.size
        for frame in ImageSequence.Iterator(image):
            self.frames.append(get_rgba_pixels(frame))
            if (duration := frame.info.get("duration", 0)) < 1:
                duration = 100
            self.durations.append(duration / 1250)
            # Technically this should be / 1000 (millis to seconds) but I found that 1250 works better...
        self.animated = len(self.durations) > 1

        image.close()
        self.loaded = True
        self.loading = False

    def apply(self):
        if self.texture_ids:
            gl.glDeleteTextures([self.texture_ids])
            self.texture_ids.clear()
        texture_gen = gl.glGenTextures(len(self.frames))
        self.texture_ids.extend([texture_gen] if len(self.frames) == 1 else texture_gen)
        for frame, texture_id in zip(self.frames, self.texture_ids):
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, self.width, self.height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, frame)
        self.frames.clear()
        self.applied = True

    @property
    def texture_id(self):
        if not self.loaded:
            if not self.loading:
                self.loading = True
                self.applied = False
                # This next self.reload() actually loads the image and does all the conversion. It takes time and resources!
                # self.reload()  # changed
                # You can (and maybe should) run this in a thread! threading.Thread(target=self.reload, daemon=True).start()
                # Or maybe setup an image thread and queue images to load one by one?
                # You could do this with https://gist.github.com/Willy-JL/bb410bcc761f8bf5649180f22b7f3b44 like so:
                sync_thread.queue(self.reload)  # changed
            return dummy_texture_id()

        if self.missing or self.invalid:
            return dummy_texture_id()

        if not self.applied:
            self.apply()

        if self.animated:
            if self.prev_time != (new_time := imgui.get_time()):
                self.prev_time = new_time
                self.elapsed += imgui.get_io().delta_time
                while (excess := self.elapsed - self.durations[max(self.frame, 0)]) > 0:
                    self.elapsed = excess
                    self.frame += 1
                    if self.frame == len(self.durations) - 1:
                        self.frame = 0

        return self.texture_ids[self.frame]

    def render(self, width: int, height: int, *args, **kwargs):
        if imgui.is_rect_visible(width, height):
            if self.animated or self.loading:  # added
                global redraw  # added
                redraw = True  # added
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
            return True
        else:
            # Skip if outside view
            imgui.dummy(width, height)
            return False

    def crop_to_ratio(self, ratio: int | float, fit=False):
        return _crop_to_ratio(self.width, self.height, ratio, fit)


# Example usage
if __name__ == "__main__":
    # Images are loaded lazily, you can create as many as you want,
    # they will only be loaded when shown for the first time.
    # GIFs are also supported!
    image = ImageHelper("example.png")
    # You can also use glob patterns, pass a folder path and add a file glob pattern:
    # image = ImageHelper("/path/to/images", glob="**/example.*")
    # Useful if you know the extension but not the name, or you know the name but not the extension

    show_bounding_rect = False
    # These are just to better illustrate cropping behavior, you don't need these in standard usage
    def draw_bounding_rect():
        draw_list = imgui.get_window_draw_list()
        draw_list.add_rect(*imgui.get_item_rect_min(), *imgui.get_item_rect_max(), imgui.get_color_u32_rgba(1, 1, 1, 1), thickness=2)

    while True:  # Your main window draw loop
        with imgui.begin("Example image"):
            scaled_width = image.width / 6
            scaled_height = image.height / 6

            _, show_bounding_rect = imgui.checkbox("Show bounding rect", show_bounding_rect)

            imgui.begin_group()
            ratio = 3.0
            imgui.text(f"Crop to ratio {ratio}:")
            image.render(scaled_width, scaled_height / ratio, *image.crop_to_ratio(ratio))
            if show_bounding_rect:
                draw_bounding_rect()

            ratio = 0.3
            imgui.text(f"Crop to ratio {ratio}:")
            image.render(scaled_width * ratio, scaled_height, *image.crop_to_ratio(ratio))
            if show_bounding_rect:
                draw_bounding_rect()

            ratio = 2.0
            imgui.text(f"Fit to ratio {ratio}:")
            image.render(scaled_width, scaled_height / ratio, *image.crop_to_ratio(ratio, fit=True))
            if show_bounding_rect:
                draw_bounding_rect()

            ratio = 0.4
            imgui.text(f"Fit to ratio {ratio}:")
            image.render(scaled_width * ratio, scaled_height, *image.crop_to_ratio(ratio, fit=True))
            if show_bounding_rect:
                draw_bounding_rect()
            imgui.end_group()

            imgui.same_line(spacing=30)

            imgui.begin_group()
            imgui.text("Scaled size:")
            image.render(scaled_width, scaled_height)
            if show_bounding_rect:
                draw_bounding_rect()

            imgui.text("Rounded corners:")
            image.render(scaled_width, scaled_height, rounding=26)
            if show_bounding_rect:
                draw_bounding_rect()

            imgui.text("Some rounded corners:")
            image.render(scaled_width, scaled_height, rounding=26, flags=imgui.DRAW_ROUND_CORNERS_TOP_LEFT | imgui.DRAW_ROUND_CORNERS_BOTTOM_RIGHT)
            if show_bounding_rect:
                draw_bounding_rect()
            imgui.end_group()

            imgui.same_line(spacing=30)

            imgui.begin_group()
            imgui.text("Actual size:")
            image.render(image.width, image.height)
            if show_bounding_rect:
                draw_bounding_rect()
            imgui.end_group()
