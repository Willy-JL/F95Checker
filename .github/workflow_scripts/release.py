import requests
import json
import os


if __name__ == "__main__":
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
    print(f"event = {json.dumps(event, indent=4)}")
    release = requests.get(
        f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/releases/{event['release']['id']}",
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {os.environ['GITHUB_TOKEN']}"
        }
    ).json()
    print(f"release = {json.dumps(release, indent=4)}")
    body = "# ⬇️ Download\n"
    for asset_type, asset_icon in [("Windows", "🪟"), ("Linux", "🐧"), ("MacOS", "🍎"), ("Source", "🐍")]:
        print(f"Adding {asset_type}")
        for asset in release["assets"]:
            if asset_type.lower() in asset["name"].lower():
                asset_url = asset["browser_download_url"]
        body += f">### [{asset_type} {asset_icon}]({asset_url}) ([VirusTotal]())\n\n"
    body += (
        "<br />\n\n" +
        "# ❤️ Support\n" +
        "F95Checker is **Free and Open Source Software**, provided to you **free of cost**. However it is actively **developed by " +
        "one single person only, WillyJL**. Please consider [**donating**](https://linktr.ee/WillyJL) or **sharing this software**!\n\n" +
        "<br />\n\n" +
        "# 🚀 Changelog\n" +
        release["body"]
    )
    print(f"Full body:\n\n{body}")
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
