import typing
import imgui

from modules.structs import MsgBox
from modules import utils

icon_font = None
popup_flags: int = (
    imgui.WINDOW_NO_MOVE |
    imgui.WINDOW_NO_RESIZE |
    imgui.WINDOW_NO_COLLAPSE |
    imgui.WINDOW_NO_SAVED_SETTINGS |
    imgui.WINDOW_ALWAYS_AUTO_RESIZE
)


def msgbox(title: str, message: str, type: MsgBox = None, buttons: dict[str, typing.Callable] = True):
    def popup_content():
        spacing = 2 * imgui.style.item_spacing.x
        if type is MsgBox.info:
            icon = "󰋼"
            color = (0.10, 0.69, 0.95)
        elif type is MsgBox.warn:
            icon = "󱇎"
            color = (0.95, 0.69, 0.10)
        elif type is MsgBox.error:
            icon = "󰀩"
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
        msg_size = imgui.calc_text_size(message)
        if icon and (diff := icon_size.y - msg_size.y) > 0:
            imgui.dummy(0, diff / 2 - imgui.style.item_spacing.y)
        imgui.text_unformatted(message)
        imgui.end_group()
        imgui.same_line(spacing=spacing)
        imgui.dummy(0, 0)
    return utils.popup(title, popup_content, buttons, closable=False, outside=False)


class Exc(Exception):
    def __init__(self, title:str, message: str, type=MsgBox.error, buttons: dict[str, typing.Callable] = None):
        utils.push_popup(msgbox, title, message, type, buttons)
        super().__init__(message)
