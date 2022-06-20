# https://gist.github.com/Willy-JL/9c5116e5a11abd559c56f23aa1270de9
from PIL import Image, ImageSequence, UnidentifiedImageError
import OpenGL.GL as gl
import pathlib
import imgui
import numpy

from modules import sync_thread


class ImageHelper:
    def __init__(self, path: str | pathlib.Path, glob=""):
        self.width = 1
        self.height = 1
        self.glob = glob
        self.loaded = False
        self.loading = False
        self.applied = False
        self.missing = False
        self.frame_count = 1
        self.animated = False
        self.prev_time = 0.0
        self.current_frame = -1
        self.frame_elapsed = 0.0
        self.data: bytes | list[bytes] = None
        self._texture_id: numpy.uint32 = None
        self.frame_durations: list[float] = None
        self.path = pathlib.Path(path)
        self.resolved_path: pathlib.Path = None
        self.resolve()

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

    def resolve(self):
        self.resolved_path = self.path
        if self.glob:
            paths = list(self.resolved_path.glob(self.glob))
            if not paths:
                self.set_missing()
                return
            # If you want you can setup preferred extensions like this:
            paths.sort(key=lambda path: path.suffix != ".gif")
            # This will prefer .gif files!
            self.resolved_path = paths[0]
        if self.resolved_path.is_file():
            self.missing = False
        else:
            self.set_missing()
            return

    def reload(self):
        self.resolve()
        if self.missing:
            return
        try:
            image = Image.open(self.resolved_path)
        except UnidentifiedImageError:
            self.set_missing()
            return
        self.width, self.height = image.size
        if hasattr(image, "n_frames") and image.n_frames > 1:
            self.animated = True
            self.data = []
            self.frame_durations = []
            for frame in ImageSequence.Iterator(image):
                self.data.append(self.get_rgba_pixels(frame))
                if (duration := image.info["duration"]) < 1:
                    duration = 100
                self.frame_durations.append(duration / 1250)
                # Technically this should be / 1000 (millis to seconds) but I found that 1250 works better...
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
                # This next self.reload() actually loads the image and does all the conversion. It takes time and resources!
                # self.reload()
                # You can (and maybe should) run this in a thread! threading.Thread(target=self.reload, daemon=True).start()
                # Or maybe setup an image thread and queue images to load one by one?
                # You could do this with https://gist.github.com/Willy-JL/bb410bcc761f8bf5649180f22b7f3b44
                sync_thread.queue(self.reload)
        elif not self.missing:
            if self.animated:
                if self.prev_time != (new_time := imgui.get_time()):
                    self.prev_time = new_time
                    self.frame_elapsed += imgui.get_io().delta_time
                    while (excess := self.frame_elapsed - self.frame_durations[max(self.current_frame, 0)]) > 0:
                        self.frame_elapsed = excess
                        self.applied = False
                        self.current_frame += 1
                        if self.current_frame == self.frame_count:
                            self.current_frame = 0
                if not self.applied:
                    self.apply(self.data[self.current_frame])
                    self.applied = True
            elif not self.applied:
                self.apply(self.data)
                self.applied = True
        return self._texture_id

    def render(self, width: int, height: int, *args, **kwargs):
        if self.missing:
            return False
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
            return True
        else:
            # Skip if outside view
            imgui.dummy(width, height)
            return False

    def crop_to_ratio(self, ratio: int | float, fit=False):
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
