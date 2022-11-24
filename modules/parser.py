import multiprocessing
import datetime as dt
import functools
import bs4
import re
import os

from modules.structs import MsgBox, Status, Tag, Type
from modules import error

html = functools.partial(bs4.BeautifulSoup, features="lxml")
_html = html


def is_text(text: str):
    def _is_text(elem: bs4.element.Tag):
        if not hasattr(elem, "text"):
            return False
        val = elem.text.lower().strip()
        return val == text or val == text + ":"
    return _is_text


def is_class(name: str):
    def _is_class(elem: bs4.element.Tag):
        return name in elem.get_attribute_list("class")
    return _is_class


class ParserException(Exception):
    def __init__(self, **kwargs):
        super().__init__()
        self.kwargs = kwargs


def thread(game_id: int, res: bytes, pipe: multiprocessing.Queue = None):
    def game_has_prefixes(*names: list[str]):
        for name in names:
            if head.find("span", text=f"[{name}]"):
                return True
        return False
    def get_game_attr(*names: list[str]):
        for name in names:
            if match := re.search(r"^\s*" + name + r"\s*:?\s*\n\s*:?\s*(.*)", plain, flags=re.RegexFlag.MULTILINE | re.RegexFlag.IGNORECASE):
                return match.group(1).strip()
        return ""
    def get_long_game_attr(*names: list[str]):
        for name in names:
            if elem := post.find(is_text(name)):
                break
        if not elem:
            return ""
        value = ""
        while True:
            if is_class("bbWrapper")(elem) or elem.parent.name == "article":
                break
            for sibling in elem.next_siblings:
                if sibling.name == "b" or (hasattr(sibling, "get") and "center" in sibling.get("style", "")):
                    break
                stripped = sibling.text.strip()
                if stripped == ":" or stripped == "":
                    continue
                value += sibling.text
            else:
                elem = elem.parent
                continue
            break
        value = value.strip()
        while "\n\n\n" in value:
            value = value.replace("\n\n\n", "\n\n")
        return value

    try:

        html = _html(res)
        head = html.find(is_class("p-body-header"))
        post = html.find(is_class("message-threadStarterPost"))
        if head is None or post is None:
            from main import self_path
            (self_path / f"{game_id}_broken.html").write_bytes(res)
            e = ParserException(
                title="Thread parsing error",
                msg=f"Failed to parse necessary sections in thread response, the html file has\nbeen saved to:\n{self_path}{os.sep}{game_id}_broken.html\n\nPlease submit a bug report on F95Zone or GitHub including this file.",
                type=MsgBox.error
            )
            if pipe:
                pipe.put_nowait(e)
                return
            else:
                return e
        for spoiler in post.find_all(is_class("bbCodeSpoiler-button")):
            try:
                next(spoiler.span.span.children).replace_with(html.new_string(""))
            except Exception:
                pass
        plain = post.find("article").get_text(separator="\n", strip=False)

        name = re.search(r"(?:\[[^\]]+\] - )*([^\[\|]+)", html.title.text).group(1).strip()

        version = get_game_attr("version")
        if not version:
            if match := re.search(r"(?:\[[^\]]+\] - )*[^\[]+\[([^\]]+)\]", html.title.text):
                version = match.group(1).strip()
        if not version:
            version = "N/A"

        developer = get_game_attr("developer/publisher", "developer & publisher", "developer / publisher", "developer\n/\npublisher", "original developer", "developers", "developer", "publisher", "artist", "animator", "producer", "modder", "remake by", "game by", "posted by").rstrip("(|-/").strip()

        # Content Types
        if game_has_prefixes("Cheat Mod"):
            type = Type.Cheat_Mod
        elif game_has_prefixes("Mod"):
            type = Type.Mod
        elif game_has_prefixes("Tool"):
            type = Type.Tool
        # Post Types
        elif game_has_prefixes("READ ME"):
            type = Type.READ_ME
        elif game_has_prefixes("Request"):
            type = Type.Request
        elif game_has_prefixes("Tutorial"):
            type = Type.Tutorial
        # Media Types
        elif game_has_prefixes("SiteRip"):
            type = Type.SiteRip
        elif game_has_prefixes("Collection"):
            type = Type.Collection
        elif game_has_prefixes("Manga"):
            type = Type.Manga
        elif game_has_prefixes("Comics"):
            type = Type.Comics
        elif game_has_prefixes("Video"):
            type = Type.Video
        elif game_has_prefixes("GIF"):
            type = Type.GIF
        elif game_has_prefixes("Pinup"):
            type = Type.Pinup
        elif game_has_prefixes("CG"):
            type = Type.CG
        # Game Engines
        elif game_has_prefixes("ADRIFT"):
            type = Type.ADRIFT
        elif game_has_prefixes("Flash"):
            type = Type.Flash
        elif game_has_prefixes("HTML"):
            type = Type.HTML
        elif game_has_prefixes("Java"):
            type = Type.Java
        elif game_has_prefixes("Others"):
            type = Type.Others
        elif game_has_prefixes("QSP"):
            type = Type.QSP
        elif game_has_prefixes("RAGS"):
            type = Type.RAGS
        elif game_has_prefixes("RPGM"):
            type = Type.RPGM
        elif game_has_prefixes("Ren'Py"):
            type = Type.RenPy
        elif game_has_prefixes("Tads"):
            type = Type.Tads
        elif game_has_prefixes("Unity"):
            type = Type.Unity
        elif game_has_prefixes("Unreal Engine"):
            type = Type.Unreal_Eng
        elif game_has_prefixes("WebGL"):
            type = Type.WebGL
        elif game_has_prefixes("Wolf RPG"):
            type = Type.Wolf_RPG
        else:
            type = Type.Misc

        if game_has_prefixes("Completed"):
            status = Status.Completed
        elif game_has_prefixes("Onhold"):
            status = Status.OnHold
        elif game_has_prefixes("Abandoned"):
            status = Status.Abandoned
        else:
            status = Status.Normal

        last_updated = 0
        text = get_game_attr("thread updated", "updated").replace("/", "-")
        try:
            last_updated = dt.datetime.fromisoformat(text).timestamp()
        except ValueError:
            pass
        if not last_updated:
            if elem := post.find(is_class("message-lastEdit")):
                last_updated = int(elem.find("time").get("data-time"))
            else:
                last_updated = int(post.find(is_class("message-attribution-main")).find("time").get("data-time"))
        last_updated = int(dt.datetime.fromordinal(dt.datetime.fromtimestamp(last_updated).date().toordinal()).timestamp())

        score = 0.0
        if elem := head.find("select", attrs={"name": "rating"}):
            score = float(elem.get("data-initial-rating"))
        elif elem := head.find(is_class("bratr-rating")):
            score = float(re.search(r"(\d(?:\.\d\d?)?)", elem.get("title")).group(1))

        description = get_long_game_attr("overview", "story")

        changelog = get_long_game_attr("changelog", "change-log")

        tags = []
        if (taglist := head.find(is_class("js-tagList"))) is not None:
            for child in taglist.children:
                if hasattr(child, "get") and "/tags/" in (tag := child.get("href", "")):
                    tag = tag.replace("/tags/", "").strip("/")
                    tags.append(Tag[tag])

        elem = post.find(is_class("bbWrapper")).find(lambda elem: elem.name == "img" and "data-src" in elem.attrs)
        if elem:
            image_url = elem.get("data-src")
        else:
            image_url = "-"

    except Exception:
        e = ParserException(
            title="Thread parsing error",
            msg=f"Something went wrong while parsing thread {game_id}:\n{error.text()}",
            type=MsgBox.error,
            more=error.traceback()
        )
        if pipe:
            pipe.put_nowait(e)
            return
        else:
            return e

    ret = (name, version, developer, type, status, last_updated, score, description, changelog, tags, image_url)
    if pipe:
        pipe.put_nowait(ret)
    else:
        return ret
