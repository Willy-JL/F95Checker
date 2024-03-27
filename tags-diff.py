import json

from modules import async_thread, db
from modules.structs import Tag
from modules.parser import html
from modules import api


def main():
    async_thread.setup()

    with db.setup(), api.setup():
        res = async_thread.wait(api.fetch("GET", f"{api.host}/sam/latest_alpha"))
        txt = html(res).find("body").find("script").text  # type: ignore
        txt = txt.replace("var latestUpdates =", "").replace(";", "").strip()
        obj = json.loads(txt)
        tags: dict[str, str] = obj["tags"]

    missing = []
    existing = [t.text for t in Tag]  # type: ignore
    for tag in tags.values():
        if tag not in existing:
            missing.append(tag)
    if missing:
        print("Some tags are missing:")
        for tag in missing:
            print(f"  - {tag}")
    else:
        print("All tags are up-to-date!")


if __name__ == "__main__":
    main()
