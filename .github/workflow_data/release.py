import requests
import json
import os


if __name__ == "__main__":
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
    print(f"event = {json.dumps(event, indent=4)}")
    release = requests.get(
        event["release"]["url"],
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {os.environ['GITHUB_TOKEN']}"
        }
    ).json()
    print(f"release = {json.dumps(release, indent=4)}")
    body = "## ⬇️ Download\n"
    for asset_type, asset_icon in [("Windows", "🪟"), ("Linux", "🐧"), ("MacOS", "🍎"), ("Source", "🐍")]:
        print(f"Adding {asset_type}")
        for asset in release["assets"]:
            if asset_type.lower() in asset["name"].lower():
                asset_url = asset["browser_download_url"]
        body += f">### [{asset_type} {asset_icon}]({asset_url}) ([VirusTotal](https://www.virustotal.com/gui/file/))\n\n"
    body += (
        "## ❤️ Support\n" +
        "F95Checker is **Free and Open Source Software**, provided to you **free of cost**. However it is actively **developed by " +
        "one single person only, WillyJL**. Please consider [**donating**](https://linktr.ee/WillyJL) or **sharing this software**!\n\n" +
        "## 🚀 Changelog\n" +
        release["body"]
    )
    print(f"Full body:\n\n{body}")
    req = requests.patch(
        release["url"],
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {os.environ['GITHUB_TOKEN']}"
        },
        json={
            "body": body
        }
    )
    if not req.ok:
        print(f"{req.status_code = }\n{req.content = }")
