import multiprocessing
import datetime as dt
import functools
import bs4
import re
import os

from modules.structs import (
    MsgBox,
    Status,
    Type,
    Tag,
)
from modules import (
    error,
)

html = functools.partial(bs4.BeautifulSoup, features="lxml")
_html = html

# [^\S\r\n] = whitespace but not newlines
sanitize_whitespace = lambda text: re.sub(r" *(?:\r\n?|\n)", r"\n", re.sub(r"(?:[^\S\r\n]|\u200b)", " ", text))
fixed_newlines = lambda text: re.sub(r"(?: *\n){2}(?: *\n)+", r"\n\n", text).strip()
fixed_spaces = lambda text: re.sub(r" +", r" ", text).strip()
clean_text = lambda text: fixed_spaces(fixed_newlines(sanitize_whitespace(text)))


def is_text(text: str):
    def _is_text(elem: bs4.element.Tag):
        if not hasattr(elem, "text"):
            return False
        val = sanitize_whitespace(elem.text.lower())
        return val == text or val.startswith(text + ":")
    return _is_text


def is_class(name: str):
    def _is_class(elem: bs4.element.Tag):
        return hasattr(elem, "get_attribute_list") and name in elem.get_attribute_list("class")
    return _is_class


def datestamp(timestamp: int | float):
    return int(dt.datetime.fromordinal(dt.datetime.fromtimestamp(timestamp).date().toordinal()).timestamp())


class ParserException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.args = args
        self.kwargs = kwargs


def thread(game_id: int, res: bytes, pipe: multiprocessing.Queue = None):
    def game_has_prefixes(*names: list[str]):
        for name in names:
            if head.find("span", text=f"{name}"):
                return True
        return False
    def get_game_attr(*names: list[str]):
        for name in names:
            if match := re.search(r"^ *" + name + r" *(?: *\n? *:|: *\n? *) *(.*)", plain, flags=re.RegexFlag.MULTILINE | re.RegexFlag.IGNORECASE):
                return fixed_spaces(match.group(1))
        return ""
    def get_long_game_attr(*names: list[str]):
        value_regex = ""
        for name in names:
            if match := re.search(r"^ *" + name + r" *:? *\n? *:? *((?:.|\n)*)", plain, flags=re.RegexFlag.MULTILINE | re.RegexFlag.IGNORECASE):
                value_regex = re.sub(
                    r"(?:(?: *\n){7}|(?:\n *[A-Z a-z]+:(?:.|\n)+?){2}|\n *(?:DOWNLOAD|Download) *(?:\n|:))(?:.|\n)*", r"", match.group(1),
                    flags=re.RegexFlag.MULTILINE
                )
                value_regex = fixed_newlines(value_regex)
        value_html = ""
        for name in names:
            if elem := post.find(is_text(name)):
                break
        if elem:
            while children := list(getattr(elem, "children", [])):
                elem = children[0]
            while not (is_class("bbWrapper")(elem) or elem.parent.name == "article"):
                if elem.next_sibling:
                    elem = elem.next_sibling
                else:
                    elem = elem.parent
                    continue
                if elem.name == "b" or (hasattr(elem, "get") and "center" in elem.get("style", "")):
                    break
                text = sanitize_whitespace(elem.text)
                if text.strip() in (":", ""):
                    continue
                value_html += text
            value_html = fixed_newlines(value_html)
        return value_html, value_regex
    def get_game_downloads(*names: list[str]):
        for name in names:
            if elem := post.find(is_text(name)):
                break
        if not elem:
            return []
        while not is_class("link")(elem) and (children := list(getattr(elem, "children", []))):
            elem = children[0]
        downloads = []
        download_name = ""
        download_mirrors = []
        def add_downloads():
            nonlocal download_name, download_mirrors
            download_name = clean_text(download_name)
            lines = download_name.split("\n")
            download_name = clean_text(lines.pop()).strip(":")
            while lines:
                if line := clean_text(lines.pop(0)).strip(":"):
                    downloads.append((line, []))
            if download_name or download_mirrors:
                downloads.append((download_name, download_mirrors))
                download_name = ""
                download_mirrors = []
        while not (is_class("bbWrapper")(elem) or elem.parent.name == "article"):
            if elem.next_sibling:
                elem = elem.next_sibling
            else:
                elem = elem.parent
                continue
            while not (is_link := is_class("link")(elem)) and (children := list(getattr(elem, "children", []))):
                elem = children[0]
            if is_link:
                download_mirrors.append((clean_text(elem.text), elem.get("href")))
            else:
                if elem.name in ("img", "video"):
                    break
                text = sanitize_whitespace(elem.text)
                if not text.strip("-,*:/ "):
                    continue
                if download_mirrors:
                    add_downloads()
                download_name += text
        add_downloads()
        downloads = tuple(downloads)
        return downloads

    try:

        html = _html(res)
        head = html.find(is_class("p-body-header"))
        post = html.find(is_class("message-threadStarterPost"))
        if head is None or post is None:
            from main import self_path
            (self_path / f"{game_id}_broken.html").write_bytes(res)
            e = ParserException(
                "Thread parsing error",
                "Failed to parse necessary sections in thread response, the html file has\n"
                f"been saved to:\n{self_path}{os.sep}{game_id}_broken.html\n"
                "\n"
                "Please submit a bug report on F95Zone or GitHub including this file.",
                MsgBox.error
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
        for div in post.find_all("div"):
            div.insert_after(html.new_string("\n"))
        plain = sanitize_whitespace(post.find("article").get_text(separator="", strip=False))

        name = ""
        for elem in html.find(is_class("p-title-value")).children:
            if not is_class("labelLink")(elem) and not is_class("label-append")(elem):
                name += elem.text
        name = fixed_spaces(sanitize_whitespace(re.search(r"^\s*(.*?)(?:\s*\[.*?\]\s*)*$", name).group(1)))

        thread_version = get_game_attr("version", "game version", "mod version")
        if not thread_version:
            if match := re.search(r"(?:\[.+?\] - )*.+?\[(.+?)\]", html.title.text):
                thread_version = fixed_spaces(sanitize_whitespace(match.group(1)))
        if not thread_version:
            thread_version = None

        developer = get_game_attr(
            "developer/publisher",
            "developer & publisher",
            "developer / publisher",
            "original developer",
            "developers",
            "developer",
            "publisher",
            "artist",
            "animator",
            "producer",
            "modder",
            "remake by",
            "game by",
            "posted by"
        )
        for separator in developer_chop_separators:
            developer = developer.split(separator)[0]
        while True:
            prev_developer = developer
            developer = re.sub(r"(" + r"|".join(developer_remove_patterns) + r")", r"", developer, flags=re.IGNORECASE)
            if not developer:
                developer = prev_developer
                break
            if developer == prev_developer:
                break
        developer = fixed_spaces(developer.strip(developer_strip_chars))

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
        text = get_game_attr("thread updated", "updated", "release date").replace("/", "-")
        try:
            last_updated = dt.datetime.fromisoformat(text).timestamp()
        except ValueError:
            pass
        if not last_updated:
            try:
                if elem := post.find(is_class("message-lastEdit")):
                    last_updated = int(elem.find("time").get("data-time"))
                else:
                    last_updated = int(post.find(is_class("message-attribution-main")).find("time").get("data-time"))
            except Exception:
                pass
        last_updated = datestamp(last_updated)

        score = 0.0
        if elem := head.find("select", attrs={"name": "rating"}):
            score = float(elem.get("data-initial-rating"))
        elif elem := head.find(is_class("bratr-rating")):
            score = float(re.search(r"(\d(?:\.\d\d?)?)", elem.get("title")).group(1))

        votes = 0
        if elem := html.find(is_class("tabs")):
            if match := re.search(r"reviews\s*\((\d+)\)", elem.get_text(), re.M | re.I):
                try:
                    votes = int(match.group(1))
                except Exception:
                    pass

        description_html, description_regex = get_long_game_attr("overview", "story")
        changelog_html, changelog_regex = get_long_game_attr("changelog", "change-log", "change log")
        if len(description_regex) > len(description_html):
            if description_html and description_regex in changelog_html + changelog_regex:
                description = description_html
            else:
                description = description_regex
        else:
            if description_regex and description_html in changelog_html + changelog_regex:
                description = description_regex
            else:
                description = description_html
        changelog = changelog_regex if len(changelog_regex) > len(changelog_html) else changelog_html

        tags = []
        unknown_tags = []
        if (taglist := head.find(is_class("js-tagList"))) is not None:
            for child in taglist.children:
                if hasattr(child, "get") and "/tags/" in (tag := child.get("href", "")):
                    tag = tag.replace("/tags/", "").strip("/")
                    if tag not in Tag._member_names_:
                        unknown_tags.append(tag)
                    else:
                        tags.append(Tag[tag])
        tags = tuple(sorted(tags))

        elem = post.find(is_class("bbWrapper")).find(lambda elem: elem.name == "img" and "data-src" in elem.attrs)
        if elem:
            image_url = elem.get("data-src")
        else:
            image_url = "missing"

        downloads = get_game_downloads("downloads", "download")

        os_compat = get_game_attr(
            "os",
        )
        
        operating_system = []

        if ("Android") in os_compat:
            operating_system.append("Android")

        if ("Linux") in os_compat:
            operating_system.append("Linux")

        if ("Mac") in os_compat:
            operating_system.append("Mac")

        if ("Windows") in os_compat:
            operating_system.append("Windows")

    except Exception:
        e = ParserException(
            "Thread parsing error",
            f"Something went wrong while parsing thread {game_id}:\n{error.text()}",
            MsgBox.error,
            more=error.traceback()
        )
        if pipe:
            pipe.put_nowait(e)
            return
        else:
            return e
        
    ret = (name, thread_version, developer, type, status, last_updated, score, votes, description, changelog, tags, unknown_tags, image_url, downloads, operating_system)
    if pipe:
        pipe.put_nowait(ret)
    else:
        return ret


developer_strip_chars = "-–|｜/':,([{ "

developer_chop_separators = [
    "is creating",
    "and h",
    " - ",
    " – ",
    " | ",
    " ｜ ",
    " / ",
    "'s ",
    ": ",
    ", ",
    " (",
    " [",
    " {"
]

developer_remove_patterns = [
    r"commissions?",
    r"blogspot",
    r"profile",
    r"website",
    r"trailer",
    r"weebly",
    r" blog",
    r" page",
    r" web",
    r"linktr(\.| *)?ee",
    r"instagram",
    r"facebook",
    r"youtube",
    r"discord",
    r"twitter",
    r"reddit",
    r"tumblr",
    r"buy *me *a *coffee",
    r"( |-)itch(\.io)?",
    r"subscr?ibe?star",
    r"kickstarter",
    r"tip *jar",
    r"indiegogo",
    r"gumroad",
    r"patreon",
    r"ko-?fi",
    r"fanbox",
    r"fantia",
    r"slushe",
    r"naughty *machinima",
    r"hypnopics *collective",
    r"affect3d(store)?",
    r"rule34(video)?",
    r"picarto(\.tv)?",
    r"furaffinity",
    r"newgrounds",
    r"deviantart",
    r"artstation",
    r"(porn)?3dx",
    r"redgifs?",
    r"pornhub",
    r"xvideos",
    r"pixiv",
    r"hentai-?foundry",
    r"hentaiengine",
    r"lewdpixels",
    r"waifu\.nl",
    r"bowlroll",
    r"2dmarket",
    r"ci-en",
    r"iwara",
    r"fakku",
    r" vndb",
    r" dmm",
    r"tfgames?site",
    r"f95(zone)?",
    r"gamejolt",
    r"dlsite",
    r"fenoxo",
    r"boosty",
    r"steam",
    r" enty",
    r"https?://\S*",
]
