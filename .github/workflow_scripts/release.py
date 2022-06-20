import requests
import base64
import json
import io
import os


if __name__ == "__main__":
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        release = json.load(f)
    release = requests.get(
        f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/releases/{release['id']}",
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {os.environ['GITHUB_TOKEN']}"
        }
    ).json()
    body = "# ⬇️ Download\n"
    for asset_type, asset_icon in [("Windows", "🪟"), ("Linux", "🐧"), ("MacOS", "🍎"), ("Source", "🐍")]:
        for asset in release["assets"]:
            if asset_type.lower() in asset["name"].lower():
                asset_url = asset["browser_download_url"]
        asset = requests.get(asset_url).content
        vt_temp = requests.get(
            "https://www.virustotal.com/api/v3/files/upload_url",
            headers={
                "Accept": "application/json",
                "x-apikey": os.environ["VT_API_KEY"]
            }
        )
        vt_id = requests.post(
            vt_temp,
            headers={
                "Accept": "application/json",
                "x-apikey": os.environ["VT_API_KEY"]
            },
            files={
                "file": io.BytesIO(asset)
            }
        ).json()["data"]["id"]
        vt_hash = str(base64.b64decode(vt_id), encoding="utf-8").split(":")[0]
        vt_url = f"https://www.virustotal.com/gui/file/{vt_hash}/"
        body += f">### [{asset_type} {asset_icon}]({asset_url}) ([VirusTotal]({vt_url}))\n\n"
    body += (
        "<br />\n\n" +
        "# ❤️ Support\n" +
        "F95Checker is **Free and Open Source Software**, provided to you **free of cost**. However it is actively **developed by " +
        "one single person only, WillyJL**. Please consider [**donating**](https://linktr.ee/WillyJL) or **sharing this software**!\n\n" +
        "<br />\n\n" +
        "# 🚀 Changelog\n" +
        release["body"]
    )
    requests.patch(
        f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/releases/{release['id']}",
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {os.environ['GITHUB_TOKEN']}"
        },
        data={
            "body": body
        }
    )
