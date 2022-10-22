import typing
import imgui

from modules.structs import MsgBox
from modules import globals, icons, utils

icon_font = None
popup_flags: int = (
    imgui.WINDOW_NO_MOVE |
    imgui.WINDOW_NO_RESIZE |
    imgui.WINDOW_NO_COLLAPSE |
    imgui.WINDOW_NO_SAVED_SETTINGS |
    imgui.WINDOW_ALWAYS_AUTO_RESIZE
)


def msgbox(title: str, msg: str, type: MsgBox = None, buttons: dict[str, typing.Callable] = True, more: str = None, popup_uuid: str = ""):
    def popup_content():
        spacing = 2 * imgui.style.item_spacing.x
        if type is MsgBox.info:
            icon = icons.information
            color = (0.10, 0.69, 0.95)
        elif type is MsgBox.warn:
            icon = icons.alert_rhombus
            color = (0.95, 0.69, 0.10)
        elif type is MsgBox.error:
            icon = icons.alert_octagon
            color = (0.95, 0.22, 0.22)
        else:
            icon = None
        if icon:
            imgui.push_font(icon_font)
            icon_size = imgui.calc_text_size(icon)
            imgui.text_colored(icon, *color)
            imgui.pop_font()
            imgui.same_line(spacing=spacing)
        imgui.begin_group()
        msg_size_y = imgui.calc_text_size(msg).y
        if more:
            msg_size_y += imgui.get_text_line_height_with_spacing() + imgui.get_frame_height_with_spacing()
        if icon and (diff := icon_size.y - msg_size_y) > 0:
            imgui.dummy(0, diff / 2 - imgui.style.item_spacing.y)
        imgui.text_unformatted(msg)
        if more:
            imgui.text("")
            if imgui.tree_node("More info", flags=imgui.TREE_NODE_SPAN_AVAILABLE_WIDTH):
                size = imgui.io.display_size
                more_size = imgui.calc_text_size(more)
                _36 = globals.gui.scaled(26) + imgui.style.scrollbar_size
                width = min(more_size.x + _36, size.x * 0.8 - icon_size.x)
                height = min(more_size.y + _36, size.y * 0.7 - msg_size_y)
                imgui.input_text_multiline(f"###more_info_{title}", more,  width=width, height=height, flags=imgui.INPUT_TEXT_READ_ONLY)
                imgui.tree_pop()
        imgui.end_group()
        imgui.same_line(spacing=spacing)
        imgui.dummy(0, 0)
    return utils.popup(title, popup_content, buttons, closable=False, outside=False, popup_uuid=popup_uuid)


class Exc(Exception):
    def __init__(self, title:str, msg: str, type: MsgBox = None, buttons: dict[str, typing.Callable] = True, more: str = None):
        self.title = title
        self.msg = msg
        self.popup = utils.push_popup(msgbox, title, msg, type, buttons, more)
