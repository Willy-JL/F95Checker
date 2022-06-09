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


def msgbox(title: str, message: str, type: MsgBox = None, buttons={"󰄬 Ok": None}):
    if not imgui.is_popup_open(title):
        imgui.open_popup(title)
    closed = False
    opened = 1
    utils.constrain_next_window()
    utils.center_next_window()
    if imgui.begin_popup_modal(title, True, flags=popup_flags)[0]:
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
        imgui.begin_group()
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
        imgui.end_group()
        imgui.spacing()
        btns_width = sum(imgui.calc_text_size(label).x for label in buttons) + (2 * len(buttons) * imgui.style.frame_padding.x) + (imgui.style.item_spacing.x * (len(buttons) - 1))
        cur_pos_x = imgui.get_cursor_pos_x()
        new_pos_x = cur_pos_x + imgui.get_content_region_available_width() - btns_width
        if new_pos_x > cur_pos_x:
            imgui.set_cursor_pos_x(new_pos_x)
        for label, callback in buttons.items():
            if imgui.button(label):
                if callback:
                    callback()
                imgui.close_current_popup()
                closed = True
            imgui.same_line()
    else:
        opened = 0
        closed = True
    return opened, closed
