# https://gist.github.com/Willy-JL/9c5116e5a11abd559c56f23aa1270de9
import functools
import gc
import pathlib
import struct
import subprocess
import tempfile
import weakref

from PIL import (
    Image,
    ImageSequence,
    UnidentifiedImageError
)
from OpenGL.GL.KHR import texture_compression_astc_ldr as gl_astc
import OpenGL.GL as gl
import imgui

from external import sync_thread
from modules.api import temp_prefix
from modules import globals

redraw = False
_apply_texture_queue = []
_dummy_texture_id = None


def post_draw():
    # Max 1 apply per fram, mitigates stutters
    if _apply_texture_queue:
        _apply_texture_queue.pop(0)()
    # Unload images if not visible
    if globals.settings.unload_offscreen_images:
        hidden = globals.gui.minimized or globals.gui.hidden
        for image in ImageHelper.instances:
            if hidden or not image.shown:
                if image.applied:
                    image.unload()
            else:
                image.shown = False


def dummy_texture_id():
    global _dummy_texture_id
    if _dummy_texture_id is None:
        _dummy_texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, _dummy_texture_id)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, 0, 0, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, b"\x00\x00\x00\xff")
    return _dummy_texture_id


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
    instances = weakref.WeakSet()

    __slots__ = (
        "width",
        "height",
        "frame",
        "glob",
        "elapsed",
        "loaded",
        "loading",
        "applied",
        "missing",
        "invalid",
        "prev_time",
        "animated",
        "textures",
        "durations",
        "texture_ids",
        "resolved_path",
        "path",
        "shown",
        "__weakref__",
    )

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
        self.textures: list[bytes] = []
        self.durations: list[float] = []
        self.texture_ids: list[int] = []
        self.resolved_path: pathlib.Path = None
        self.path: pathlib.Path = pathlib.Path(path)
        self.shown = False
        type(self).instances.add(self)

    def resolve(self):
        self.resolved_path = self.path

        if self.glob:
            paths = list(self.resolved_path.glob(self.glob))
            if not paths:
                self.missing = True
                return
            if globals.settings.astc_compression:
                # Prefer .aastc files, then .gif, then anything else
                sorting = lambda path: 1 if path.suffix == ".aastc" else 2 if path.suffix == ".gif" else 3
            else:
                # Prefer .gif files, then anything else
                sorting = lambda path: path.suffix != ".gif"
            paths.sort(key=sorting)
            self.resolved_path = paths[0]

        # Choose .aastc file by same name if not already using it
        if globals.settings.astc_compression and self.resolved_path.suffix != ".aastc":
            aastc_path = self.resolved_path.with_suffix(".aastc")
            if aastc_path.is_file():
                self.resolved_path = aastc_path

        self.missing = not self.resolved_path.is_file()

    def reload(self):
        self.loaded = False
        self.loading = True
        self.applied = False
        self.resolve()

        self.frame = -1
        self.elapsed = 0.0
        self.textures.clear()
        self.invalid = False
        self.animated = False
        self.durations.clear()
        self.width, self.height = (1, 1)

        if self.missing:
            self.loaded = True
            self.loading = False
            return

        if globals.settings.astc_compression and self.resolved_path.suffix != ".aastc":
            # Compress to ASTC
            astcenc = globals.self_path / "astcenc-avx2.exe"
            astc_path = pathlib.Path(tempfile.mktemp(prefix=temp_prefix, suffix=".astc"))
            png_path = pathlib.Path(tempfile.mktemp(prefix=temp_prefix, suffix=".png"))
            aastc_path = self.resolved_path.with_suffix(".aastc")
            def astc_compress_one(src_path: pathlib.Path):
                try:
                    subprocess.check_output([astcenc, "-cl", src_path, astc_path, "6x6", "80", "-perceptual", "-silent"], stderr=subprocess.STDOUT)
                    astc = astc_path.read_bytes()
                    return astc, b""
                except subprocess.CalledProcessError as exc:
                    error = exc.stdout or "Unknown error"
                    return b"", error
                finally:
                    astc_path.unlink(missing_ok=True)

            astc, error = astc_compress_one(self.resolved_path)
            if astc:
                # Compressed with astcenc, just convert to aastc
                texture = astc[16:]
                aastc = b"".join((
                    b"\xA3\xAB\xA1\x5C",  # Magic
                    astc[4:16],  # Header
                    struct.pack("<Q", len(texture)),  # Texture length
                    struct.pack("<I", 0),  # Frame duration
                    texture,  # Texture data
                ))
                aastc_path.write_bytes(aastc)
                self.resolved_path = aastc_path
            else:
                if b"unknown image type" not in error:
                    # Something else went wrong, bail
                    self.invalid = True
                    self.loaded = True
                    self.loading = False
                    return

                # Can't compress with astcenc, convert each frame to png then compress
                try:
                    image = Image.open(self.resolved_path)
                except UnidentifiedImageError:
                    self.invalid = True
                    self.loaded = True
                    self.loading = False
                    return

                try:
                    aastc = b"\xA3\xAB\xA1\x5C"  # Magic
                    for i, frame in enumerate(ImageSequence.Iterator(image)):
                        frame.save(png_path, "PNG")
                        astc, error = astc_compress_one(png_path)
                        if not astc:
                            self.invalid = True
                            self.loaded = True
                            self.loading = False
                            return
                        if i == 0:
                            aastc += astc[4:16]  # Header
                        texture = astc[16:]
                        duration = frame.info.get("duration", 0)
                        aastc += b"".join((
                            struct.pack("<Q", len(texture)),  # Texture length
                            struct.pack("<I", duration),  # Frame duration
                            texture,  # Texture data
                        ))
                    aastc_path.write_bytes(aastc)
                finally:
                    png_path.unlink(missing_ok=True)

                image.close()

        if self.resolved_path.suffix == ".aastc":
            # ASTC file but with multiple payloads and durations, for animated textures
            aastc = self.resolved_path.read_bytes()
            head = aastc[0:16]
            magic = head[0:4]
            assert magic == b"\xA3\xAB\xA1\x5C"

            block_x = head[4]
            block_y = head[5]
            assert f"{block_x}x{block_y}" == "6x6"
            block_z = head[6]
            assert block_z == 1, block_z

            dim_x = struct.unpack("<I", head[7:10] + b"\0")[0]
            dim_y = struct.unpack("<I", head[10:13] + b"\0")[0]
            dim_z = struct.unpack("<I", head[13:16] + b"\0")[0]
            assert dim_z == 1, dim_z
            self.width = dim_x
            self.height = dim_y

            frames_data = aastc[16:]
            data_pos = 0
            while data_pos < len(frames_data):
                texture_len = struct.unpack("<Q", frames_data[data_pos:data_pos + 8])[0]
                data_pos += 8
                duration = struct.unpack("<I", frames_data[data_pos:data_pos + 4])[0]
                data_pos += 4
                texture = frames_data[data_pos:data_pos + texture_len]
                data_pos += texture_len
                self.textures.append((texture, gl_astc.GL_COMPRESSED_RGBA_ASTC_6x6_KHR))
                if duration < 1:
                    duration = 100
                self.durations.append(duration / 1000)
            self.animated = len(self.textures) > 1

            if self.glob and globals.settings.astc_compression and globals.settings.astc_replace:
                paths = list(self.path.glob(self.glob))
                if len(paths) > 1:
                    try:
                        for path in paths:
                            if path != self.resolved_path:
                                path.unlink(missing_ok=True)
                    except Exception:
                        pass

            self.loaded = True
            self.loading = False
            _apply_texture_queue.append(self.apply)
            return

        # Fallback to RGBA loading
        try:
            image = Image.open(self.resolved_path)
        except UnidentifiedImageError:
            self.invalid = True
            self.loaded = True
            self.loading = False
            return

        self.width, self.height = image.size
        for frame in ImageSequence.Iterator(image):
            if frame.mode == "RGB":
                texture = frame.tobytes("raw", "RGBX")
            elif frame.mode == "RGBA":
                texture = frame.tobytes("raw", "RGBA")
            else:
                texture = frame.convert("RGBA").tobytes("raw", "RGBA")
            self.textures.append((texture, gl.GL_RGBA))
            if (duration := frame.info.get("duration", 0)) < 1:
                duration = 100
            self.durations.append(duration / 1000)
        self.animated = len(self.textures) > 1

        image.close()
        self.loaded = True
        self.loading = False
        _apply_texture_queue.append(self.apply)

    def apply(self):
        if self.texture_ids:
            gl.glDeleteTextures([self.texture_ids])
            self.texture_ids.clear()
        texture_gen = gl.glGenTextures(len(self.textures))
        self.texture_ids.extend([texture_gen] if len(self.textures) == 1 else texture_gen)
        for (texture, texture_format), texture_id in zip(self.textures, self.texture_ids):
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER)
            if texture_format == gl_astc.GL_COMPRESSED_RGBA_ASTC_6x6_KHR:
                gl.glCompressedTexImage2D(gl.GL_TEXTURE_2D, 0, texture_format, self.width, self.height, 0, texture)
            elif texture_format == gl.GL_RGBA:
                gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, texture_format, self.width, self.height, 0, texture_format, gl.GL_UNSIGNED_BYTE, texture)
        self.textures.clear()
        self.applied = True
        gc.collect()

    def unload(self):
        if self.applied and self.texture_ids:
            gl.glDeleteTextures([self.texture_ids])
            self.texture_ids.clear()
            self.loaded = False

    @property
    def texture_id(self):
        self.shown = True

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
            return dummy_texture_id()

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
            if self.animated or self.loading:
                global redraw
                redraw = True
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
