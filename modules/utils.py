import OpenGL.GL as gl
import traceback
import imgui
import glfw
import sys
import re


def extract_thread_ids(text: str):
    ids = []
    for match in re.finditer("threads/(?:[^\./]*\.)?(\d+)", text):
        ids.append(int(match.group(1)))
    return ids


# https://gist.github.com/Willy-JL/f733c960c6b0d2284bcbee0316f88878
def get_traceback():
    exc_info = sys.exc_info()
    tb_lines = traceback.format_exception(*exc_info)
    tb = "".join(tb_lines)
    return tb


# https://github.com/pyimgui/pyimgui/blob/24219a8d4338b6e197fa22af97f5f06d3b1fe9f7/doc/examples/integrations_glfw3.py
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
