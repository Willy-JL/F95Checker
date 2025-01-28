import asyncio
import concurrent
import datetime as dt
import functools
import io
import random
import re
import time
import typing

from PIL import Image
import desktop_notifier
import glfw
import imgui

from common.structs import (
    Game,
    Label,
    MsgBox,
    Popup,
    Status,
    Tab,
    Tag,
    TimelineEvent,
    TimelineEventType,
    Type,
    ThreadMatch,
    SearchLogic,
    ExeState,
)
from external import async_thread
from modules import (
    api,
    callbacks,
    globals,
    icons,
    msgbox,
    notification_proc,
)


@functools.cache
def bayesian_average(avg_rating, num_votes):
    W, C = 100, 0
    return ((num_votes * avg_rating) + (W * C)) / (num_votes + W)


def rand_num_str(len=8):
    return "".join((random.choice('0123456789') for _ in range(len)))


# https://stackoverflow.com/a/1094933
def sizeof_fmt(num, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


@functools.cache
def map_range(in_value: float, in_start: float, in_end: float, out_start: float, out_end: float):
    in_value -= in_start
    in_end -= in_start
    in_start = 0.0
    out_range = out_end - out_start
    out_value = ((in_value / in_end) * out_range) + out_start
    return out_value


def image_ext(data: bytes):
    try:
        ext = str(Image.open(io.BytesIO(data)).format or "img").lower()
    except Exception:
        ext = "img"
    return ext


def custom_id():
    if globals.games:
        return min(min(game.id for game in globals.games.values()), 0) - 1
    else:
        return -1


def is_uri(text: str):
    # See https://www.rfc-editor.org/rfc/rfc3986#section-3.1
    return bool(re.search(r"^[A-Za-z][A-Za-z0-9\+\-\.]*://", text))


def is_refreshing():
    if globals.refresh_task and not globals.refresh_task.done():
        return True
    return False


def start_refresh_task(coro: typing.Coroutine, reset_bg_timers=True, notify_new_games=True):
    if is_refreshing():
        return
    if reset_bg_timers:
        globals.gui.bg_mode_timer = None
        globals.gui.bg_mode_notifs_timer = None
    globals.refresh_progress = 0
    globals.refresh_total = 1
    globals.gui.refresh_ratio_smooth = 0.0
    async def coro_wrapper():
        await coro
        await asyncio.sleep(0.5)
    globals.refresh_task = async_thread.run(coro_wrapper())
    globals.gui.tray.update_status()
    def done_callback(future: asyncio.Future):
        globals.refresh_task = None
        globals.gui.tray.update_status()
        globals.gui.recalculate_ids = True
        if notify_new_games and (globals.new_updated_games or globals.updated_games):
            if globals.new_updated_games:
                globals.updated_games.update(globals.new_updated_games)
                first = list(globals.new_updated_games.keys())[0]
                globals.new_updated_games.clear()
            else:
                first = list(globals.updated_games.keys())[0]
            globals.updated_games_sorted_ids = sorted(globals.updated_games.keys(), key=lambda id: globals.games[id].type.category.value)
            for popup in globals.popup_stack:
                if popup.func is type(globals.gui).draw_updates_popup:
                    globals.popup_stack.remove(popup)
            push_popup(type(globals.gui).draw_updates_popup, globals.gui).uuid = "updates"
            if globals.gui.hidden or not globals.gui.focused:
                image = list(filter(lambda f: f.suffix != ".aastc", globals.images_path.glob(f"{first}.*")))
                if image:
                    image = desktop_notifier.Attachment(path=image[0])
                else:
                    image = None
                count = len(globals.updated_games)
                notification_proc.notify(
                    title="Updates",
                    msg=f"{count} item{'' if count == 1 else 's'} in your library {'has' if count == 1 else 'have'} received updates!",
                    attachment=image,
                )
        # Continues after this only if the task was not cancelled
        try:
            future.exception()
        except concurrent.futures.CancelledError:
            return
        if globals.last_update_check is not None and globals.last_update_check < time.time() - 21600:  # Check updates after refreshing at 6 hour intervals
            from modules import api
            globals.last_update_check = None
            update_check = async_thread.run(api.check_updates())
            def reset_timer(_):
                if globals.last_update_check is None:
                    globals.last_update_check = 0.0
            update_check.add_done_callback(reset_timer)
    globals.refresh_task.add_done_callback(done_callback)


def validate_geometry(x, y, width, height):
    window_pos = (x, y)
    window_size = (width, height)
    valid = True
    for monitor in glfw.get_monitors():
        valid = False
        monitor_area = glfw.get_monitor_workarea(monitor)
        monitor_pos = (monitor_area[0], monitor_area[1])
        monitor_size = (monitor_area[2], monitor_area[3])
        # Horizontal check, at least 1 pixel on x axis must be in monitor
        if (window_pos[0]) >= (monitor_pos[0] + monitor_size[0]):
            continue  # Too right
        if (window_pos[0] + window_size[0]) <= (monitor_pos[0]):
            continue  # Too left
        # Vertical check, at least the pixel above window must be in monitor (titlebar)
        if (window_pos[1] - 1) >= (monitor_pos[1] + monitor_size[1]):
            continue  # Too low
        if (window_pos[1]) <= (monitor_pos[1]):
            continue  # Too high
        valid = True
        break
    return valid


def center_next_window():
    size = imgui.io.display_size
    imgui.set_next_window_position(size.x / 2, size.y / 2, pivot_x=0.5, pivot_y=0.5)


def constrain_next_window():
    size = imgui.io.display_size
    imgui.set_next_window_size_constraints((0, 0), (size.x * 0.9, size.y * 0.9))


def close_weak_popup():
    if imgui.is_topmost():
        # This is the topmost popup
        if imgui.io.keys_down[glfw.KEY_ESCAPE]:
            # Escape is pressed
            imgui.close_current_popup()
            return True
        elif imgui.is_mouse_clicked():
            # Mouse was just clicked
            pos = imgui.get_window_position()
            size = imgui.get_window_size()
            if size.x > 50 and size.y > 50:
                # Valid geometry
                if not imgui.is_mouse_hovering_rect(pos.x, pos.y, pos.x + size.x, pos.y + size.y, clip=False):
                    # Popup is not hovered
                    imgui.close_current_popup()
                    return True
    return False


def text_context(obj: object, attr: str, setter_extra: typing.Callable = lambda _: None, editable=True, no_icons=False):
    getter = lambda: getattr(obj, attr)
    setter = lambda val: [setattr(obj, attr, val), setter_extra(val)]
    if imgui.selectable(f"{icons.content_copy} Copy", False)[0]:
        callbacks.clipboard_copy(getter())
    if editable:
        if imgui.selectable(f"{icons.content_paste} Paste", False)[0]:
            setter(getter() + callbacks.clipboard_paste())
        if imgui.selectable(f"{icons.trash_can_outline} Clear", False)[0]:
            setter("")
        if no_icons:
            return
        if imgui.selectable(f"{icons.tooltip_image_outline} Icons", False)[0]:
            search = type("_", (), dict(_=""))()
            def popup_content():
                nonlocal search
                imgui.set_next_item_width(-imgui.FLOAT_MIN)
                _, search._ = imgui.input_text_with_hint(f"###text_context_icons_search", "Search icons...", search._)
                if imgui.begin_popup_context_item(f"###text_context_icons_search_context"):
                    text_context(search, "_", no_icons=True)
                    imgui.end_popup()
                imgui.begin_child(f"###text_context_icons_frame", width=globals.gui.scaled(350), height=imgui.io.display_size.y * 0.5)
                for name, icon in icons.names.items():
                    if not search._ or search._ in name or search._ in icon:
                        if imgui.selectable(f"{icon}  {name}", False, flags=imgui.SELECTABLE_DONT_CLOSE_POPUPS)[0]:
                            setter(getter() + icon)
                imgui.end_child()
            push_popup(
                popup, "Select icon",
                popup_content,
                buttons=True,
                closable=True,
                outside=True
            )


@functools.cache
def clean_thread_url(url: str):
    thread = re.search(r"threads/([^/]*)", url).group(1)
    return f"{api.f95_threads_page}{thread}/"


def extract_thread_matches(text: str) -> list[ThreadMatch]:
    matches = []
    if not isinstance(text, str):
        return matches
    for match in re.finditer(r"threads/(?:([^\./]*)\.)?(\d+)", text):
        matches.append(ThreadMatch(title=match.group(1) or "", id=int(match.group(2))))
    return matches

def parse_search(search: str) -> SearchLogic:
    delims = r"((?<!\\)\".*?[^\\]\"|(?<!\\)[\(\)]|[:<=>]+)| "
    search = re.sub(r"=(?=[<=>])", "", re.sub(r":", r"=", search))
    tokens = [s for s in re.split(delims, search) if s]
    return flatten_query(create_query(tokens))

def create_query(query: list[str]) -> SearchLogic:
    head = SearchLogic()
    invert: bool = False
    while len(query) > 0:
        token = query.pop(0)
        match token:
            case "(":
                new_query = create_query(query)
                head.nodes.append(new_query)
            case ")":
                break
            case "and" | "&&" | "&" | "+":
                continue
            case "<>" | "not" | "!" | "-" | "~":
                invert = not invert
            case _:
                new_query: SearchLogic = None
                logic: str = None
                type: str = "?"
                if token in ["or", "||", "|", "<", "<=", "=", ">", ">="]:
                    logic = "|"
                    type = token if token not in ["or", "||"] else "|"
                    token = None
                elif (token.startswith("\"") and token.endswith("\"")):
                    token = token[1:-1]
                new_query = SearchLogic(token, logic, invert, type)
                invert = False
                head.nodes.append(new_query)
    i: int = 0
    # Check data logic
    while i < len(head.nodes):
        token = head.nodes.pop(i)
        if (token.type[0] in ["<", "=", ">"]) & (i > 0) & (i < len(head.nodes)):
            last_query: SearchLogic = head.nodes[i - 1]
            # Only if first node
            if len(last_query.nodes) == 0:
                head.nodes.pop(i - 1)
                token.token = last_query.token
                # Tag and Label default to AND
                if token.token in ["tag", "label", "is", "all"]: token.logic = "&"
                token.invert = last_query.invert != token.invert
                found: SearchLogic = None
                if token.type == "=":
                    # Check if there is another similar data query already
                    for node in head.nodes[:i-1]:
                        if node.__eq__(token):
                            token = found = node
                            break
                if not found:
                    head.nodes.insert(i - 1, token)
                last_query = token
            if i < len(head.nodes):
                new_node = head.nodes.pop(i)
                match new_node.token:
                    case "true" | "yes":
                        new_node.token = "True"
                    case "false" | "no":
                        new_node.token = "False"
                last_query.nodes.append(new_node)
        else:
            head.nodes.insert(i, token)
            i += 1
    # Check OR logic
    i = 0
    while i < len(head.nodes):
        token = head.nodes.pop(i)
        if (token.type == "|") & (i > 0):
            or_query: SearchLogic = head.get(token, i)
            if len(or_query.nodes) == 0: or_query.nodes.append(head.nodes.pop(i - 1))
            if i < len(head.nodes):
                or_query.nodes.append(head.nodes.pop(i))
        else:
            head.nodes.insert(i, token)
            i += 1
    return head

def flatten_query(head: SearchLogic) -> SearchLogic:
    if (head.type == "?") or (len(head.nodes) == 0):
        return head
    if len(head.nodes) == 1:
        node = head.nodes.pop()
        if head.type == "=":
            if node.type == "?":
                head.nodes.append(node)
                return head
            node.token = head.token
            node.invert = (node.invert != head.invert)
            node.type = "="
            return flatten_query(node)
        elif head.type in ["|", "&"]:
            if node.type == "=":
                node.logic = head.logic
            node.invert = (node.invert != head.invert)
            return flatten_query(node)
        else:
            head.nodes.append(node)
    i = 0
    while i < len(head.nodes):
        node = head.nodes.pop(i)
        if (head.type == "=") and (node.type in ["|", "&", "="]):
            node.type = "="
            node.token = head.token
            node = flatten_query(node)
            if (node.logic != head.logic) or (node.invert != head.invert) or (head.token != node.token):
                new_node = SearchLogic(logic=head.logic, invert=head.invert, type=head.logic)
                head.invert = False
                new_node.nodes.append(head)
                new_node.nodes.append(node)
                return flatten_query(new_node)
        else:
            node = flatten_query(node)
        if node == head:
            head.nodes.extend(node.nodes)
        else:
            head.nodes.insert(i, node)
            i += 1
    return head
    

def parse_query(head: SearchLogic, base_ids: set[int]) -> set[int]:
    def attr_for(token: str, game: Game = None):
        match token:
            # Boolean matches
            case "archived":
                return game.archived
            case "custom":
                return game.custom
            case "updated":
                return game.updated
            case "outdated":
                return game.installed not in ["", game.version]
            case "exe":
                return bool(game.executables), game.executables_valid
            case "image":
                return not game.image.missing,  not game.image.invalid
            # Number matches
            case "id":
                return game.id
            case "rating":
                return game.rating
            case "score":
                return game.score
            case "votes":
                return game.votes
            case "wscore" | "weight" | "scoreweight" | "weightedscore":
                return bayesian_average(game.score, game.votes)
            # Enum matches
            case "tab":
                if game: return game.tab
                return Tab.instances
            case "status":
                if game: return game.status
                return Status
            case "type":
                if game: return game.type
                return Type
            # String matches
            case "name" | "title":
                return game.name.lower()
            case "dev" | "developer":
                return game.developer.lower()
            case "ver" | "version":
                return game.version.lower()
            case "note" | "notes":
                return game.notes.lower()
            case "url":
                return game.url.lower()
            case "desc" | "description":
                return game.description.lower()
            # Date matches
            case "added":
                return game.added_on.value
            case "updated":
                return game.last_updated.value
            case "launched":
                return game.last_launched.value
            # Timeline matches
            case "finished":
                if game: return game.finished
                return TimelineEventType.GameFinished
            case "isfinished":
                return game.finished, (game.installed or game.version)
            case "installed":
                if game: return game.installed
                return TimelineEventType.GameInstalled
            case "isinstalled":
                return game.installed, game.version
            # List matches
            case "exes" | "executables":
                return game.executables
            case "tags":
                return game.tags
            case "labels":
                return game.labels
            case "downloads":
                return set([mirror.lower() for name, mirrors in game.downloads for mirror, link in mirrors])
            case _:
                return False
    def enum_match(enums):
        for node in head.nodes:
            enum_matches = []
            regex = regexp(node.token)
            for enum in enums:
                if re.match(regex, enum.name.lower()):
                    if enum.name.lower() == node.token:
                        enum_matches = [enum]
                        break
                    enum_matches.append(enum)
            if enum_matches:
                node.token = enum_matches
    def regexp(token: str) -> str:
        regex = ".*"
        for part in token.split("*"):
            regex += re.escape(part) + ".*"
        return regex
    if head.type[0] in ["<", "=", ">"]:
        and_or = any if head.logic == "|" else all
        match head.type:
            case "<":  compare = lambda l, r: (l <  r)
            case "<=": compare = lambda l, r: (l <= r)
            case "=":  compare = lambda l, r: (l == r)
            case ">":  compare = lambda l, r: (l >  r)
            case ">=": compare = lambda l, r: (l >= r)
        if head.token in ["added", "updated", "launched", "finished", "installed"].__add__(TimelineEventType._member_names_):
            try:
                date = dt.datetime.strptime(head.nodes[0].token, globals.settings.datestamp_format)
                if head.type in ["<=", ">"]:
                    date += dt.timedelta(days=1)
                head.nodes[0].token = str(date.timestamp())
                if head.type == "=":
                    # 86400 is one day in seconds, same as dt.timedelta(days=1)
                    compare = lambda l, r: (r <= l < r + 86400)
            except ValueError:
                try:
                    float(head.nodes[0].token)
                except Exception: 
                    head.token = "is" + head.token
        match head.token:
            case "added" | "updated" | "launched" | "rating" | "score" | "votes" | "wscore" | "weight" | "scoreweight" | "weightedscore" | "id":
                key = lambda game, f: (compare(attr_for(f.token, game), float(f.nodes[0].token)))
            # Boolean matches
            case "is" | "any" | "all":
                key = lambda game, f: (and_or(attr_for(node.token, game) for node in f.nodes))
            case "archived" | "custom" | "updated":
                key = lambda game, f: (str(attr_for(head.token, game)) == f.nodes[0].token)
            # Custom matches
            case "exe" | "image":
                def key(game: Game, f: SearchLogic):
                    exists, valid = attr_for(f.token, game)
                    output: bool = f.logic == "&"
                    for node in f.nodes:
                        match node.token:
                            case "invalid":     output = exists and not valid
                            case "valid":       output = exists and valid
                            case "selected":    output = exists
                            case "unset":       output = not exists
                        if output == (f.logic == "|"):
                            return output
                    return output
            case "isfinished" | "isinstalled":
                def key(game: Game, f: SearchLogic):
                    exists, valid = attr_for(head.token, game)
                    output: bool = f.logic == "&"
                    for node in f.nodes:
                        match node.token:
                            case "True":        output = exists == valid
                            case "False":       output = exists == ""
                            case "old_version": output = exists not in ["", valid]
                            case "any":         output = bool(exists)
                        if output == (f.logic == "|"):
                            return output
                    return output
            # Tag matches
            case "tag":
                enum_match(Tag)
                key = lambda game, f: (and_or(any(tag in game.tags for tag in node.token) or (node.token in game.unknown_tags) for node in f.nodes))
            # Enum matches
            case "label":
                enum_match(Label.instances)
                key = lambda game, f: (and_or(any(label in game.labels for label in node.token) for node in f.nodes))
            case "tab" | "status" | "type":
                enum_match(attr_for(head.token))
                key = lambda game, f: (and_or(attr_for(f.token, game) in node.token for node in f.nodes))
            # String matches
            case "name" | "title" | "dev" | "developer" | "ver" | "version" | "note" | "notes" | "url" | "description" | "desc":
                key = lambda game, f: (and_or(re.match(regexp(node.token), attr_for(head.token, game)) for node in f.nodes))
            case "downloads":
                key = lambda game, f: (and_or(bool(set(filter(re.compile(regexp(node.token)).match, attr_for(head.token, game)))) for node in f.nodes))
            # List matches
            case "exes" | "executables" | "tags" | "labels":
                key = lambda game, f: (compare(len(attr_for(f.token, game)), float(f.nodes[0].token)))
            case _:
                # Timeline matches
                if head.token in TimelineEventType._member_names_.__add__(["finished", "installed"]):
                    query_type = attr_for(head.token) | TimelineEventType[head.token]
                    def key(game: Game, f: SearchLogic):
                        event = next((e for e in game.timeline_events if e.type == query_type), None)
                        return bool(event) & compare(event.timestamp.value, float(f.nodes[0].token))
                else:
                    key = None
        if key is not None:
            base_ids = set(filter(functools.partial(lambda f, k, id: f.invert != k(globals.games[id], f), head, key), base_ids))
            return base_ids
    elif head.token:
        regex = regexp(head.token)
        def key(id):
            game = globals.games[id]
            return head.invert != bool(set(filter(re.compile(regex).match, [game.version.lower(), game.developer.lower(), game.name.lower(), game.notes.lower()])))
    elif head.type in ["|", "&"]:
        queries: set[int] = set() if head.type == "|" else base_ids
        for node in head.nodes:
            new_query = parse_query(node, base_ids)
            queries = queries.union(new_query) if head.type == "|" else queries.intersection(new_query)
        key = lambda id: (head.invert != (id in queries))
    else:
        return []
    base_ids = set(filter(key, base_ids))
    return base_ids

popup_flags: int = (
    imgui.WINDOW_NO_MOVE |
    imgui.WINDOW_NO_RESIZE |
    imgui.WINDOW_NO_COLLAPSE |
    imgui.WINDOW_NO_SAVED_SETTINGS
)

def popup(label: str, popup_content: typing.Callable, buttons: dict[str, typing.Callable] = None, closable=True, outside=True, footer="", resize=True, popup_uuid: str = ""):
    if buttons is True:
        buttons = {
            f"{icons.check} Ok": None
        }
    label = label + "###popup_" + popup_uuid
    if not imgui.is_popup_open(label):
        imgui.open_popup(label)
    closed = False
    opened = 1
    constrain_next_window()
    center_next_window()
    if imgui.begin_popup_modal(label, closable or None, flags=popup_flags | (resize and imgui.WINDOW_ALWAYS_AUTO_RESIZE))[0]:
        imgui.begin_group()
        closed = (popup_content() is True) or closed  # Close if content returns True
        imgui.end_group()
        imgui.spacing()
        if buttons or footer:
            right_width = 0
            if footer:
                right_width += imgui.calc_text_size(footer).x
            if buttons:
                right_width += (
                    sum(imgui.calc_text_size(name).x for name in buttons) +
                    (2 * len(buttons) * imgui.style.frame_padding.x) +
                    (imgui.style.item_spacing.x * (len(buttons) - (not footer)))
                )
            cur_pos_x = imgui.get_cursor_pos_x()
            new_pos_x = cur_pos_x + imgui.get_content_region_available_width() - right_width
            if new_pos_x > cur_pos_x:
                imgui.set_cursor_pos_x(new_pos_x)
            if footer:
                imgui.align_text_to_frame_padding()
                imgui.text(footer)
                imgui.same_line()
            if buttons:
                for text, callback in buttons.items():
                    if imgui.button(text):
                        if callback:
                            callback()
                        imgui.close_current_popup()
                        closed = True
                    imgui.same_line()
        if outside:
             closed = closed or close_weak_popup()
    else:
        opened = 0
        closed = True
    return opened, closed


def push_popup(*args, bottom=False, **kwargs):
    popup = Popup(*args, **kwargs)
    if globals.gui:
        if (globals.gui.hidden or not globals.gui.focused) and (len(args) > 3) and (args[0] is msgbox.msgbox) and (args[3] in (MsgBox.warn, MsgBox.error)):
            # Ignore some temporary errors in background mode, taken from modules/api.py
            if globals.gui.hidden and args[1] in (
                "Rate limit",
                "Server downtime",
            ):
                return
            notification_proc.notify(
                title="Oops",
                msg="Something went wrong! Click to view the error.",
                icon=desktop_notifier.Icon(globals.self_path / "resources/icons/error.png")
            )
    if bottom:
        globals.popup_stack.insert(0, popup)
    else:
        globals.popup_stack.append(popup)
    return popup
