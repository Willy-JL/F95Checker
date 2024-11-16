import os
import sys
import json

from modules import async_thread, db, globals
from modules.structs import Tag
from modules.parser import html
from modules import api


def main():
    async_thread.setup()

    with db.setup(), api.setup():
        if xf_user := os.environ.get("XF_USER", None):
            globals.cookies["xf_user"] = xf_user
        if xf_tfa_trust := os.environ.get("XF_TFA_TRUST", None):
            globals.cookies["xf_tfa_trust"] = xf_tfa_trust
        res = async_thread.wait(api.fetch("GET", f"{api.f95_host}/sam/latest_alpha"))
        try:
            txt = html(res).find("body").find("script").text  # type: ignore
        except Exception:
            print("Failed to authenticate! Your auth cookies are stale or missing.")
            sys.exit(1)
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
        sys.exit(1)
    else:
        print("All tags are up-to-date!")
        sys.exit(0)


if __name__ == "__main__":
    main()
