const rpcPort = 57095;
const rpcURL = `http://localhost:${rpcPort}`;
let games = [];


const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));


const rpcCall = async (method, path, body, tabId) => {
    try {
        const res = await fetch(`${rpcURL}${path}`, {
            method: method,
            body: body
        });
        if (!res.ok) {
            throw res.status;
        }
        return res;
    } catch {
        if (tabId) {
            chrome.scripting.executeScript({
                target: { tabId: tabId },
                func: () => { alert("Could not connect to F95Checker!\nIs it open and updated? Is RPC enabled?") }
            });
        }
    }
}


const getGames = async () => {
    const res = await rpcCall("GET", "/games");
    games = res ? await res.json() : [];
}


const addGame = async (url, tabId) => {
    await rpcCall("POST", "/games/add", JSON.stringify([url]), tabId);
    await sleep(0.5 * 1000)
    await updateIcons(tabId);
}


// Add library icons for added games
const updateIcons = async (tabId) => {
    await getGames();
    chrome.scripting.executeScript({
        target: { tabId: tabId },
        func: (games) => {
            const threadId = (url) => {
                const match = /threads\/(?:(?:[^\.\/]*)\.)?(\d+)/.exec(url);
                return match ? parseInt(match[1]) : null;
            }
            const createIcon = (isImage) => {
                const icon = document.createElement("i");
                icon.classList.add("fa", "fa-box-heart", "f95checker-library-icon");
                icon.style.fontFamily = "'Font Awesome 5 Pro'";
                icon.style.color = "#FD5555";
                if (isImage) {
                    icon.style.position = "absolute";
                    icon.style.zIndex = "50";
                    icon.style.right = "5px";
                    icon.style.top = "5px";
                    icon.style.fontSize = "larger";
                    icon.style.background = "#262626";
                    icon.style.border = "solid #262626";
                    icon.style.borderWidth = "4px 5px";
                    icon.style.borderRadius = "4px";
                } else {
                    icon.style.marginRight = "0.2em"
                }
                icon.setAttribute("title", "This game is present in your F95Checker library!");
                icon.addEventListener("click", () => {
                    alert("This game is present in your F95Checker library!");
                });
                return icon;
            }
            const doUpdate = () => {
                for (elem of document.getElementsByClassName("f95checker-library-icon")) {
                    elem.remove();
                }
                let done = [];
                for (elem of document.querySelectorAll('a[href*="/threads/"]')) {
                    const id = threadId(elem.href);
                    if (!id || !games.includes(id)) {
                        continue;
                    }
                    let isDone = false;
                    for (doneElem of done) {
                        if (doneElem.contains(elem)) {
                            isDone = true;
                            break;
                        }
                    }
                    if (isDone) {
                        continue;
                    }
                    const isImage = elem.classList.contains("resource-tile_link") || elem.parentNode.parentNode.classList.contains("es-slides");
                    if (!isImage && !elem.href.endsWith("/unread")) {
                        continue;
                    }
                    done.push(elem.parentNode);
                    elem.insertAdjacentElement("beforebegin", createIcon(isImage));
                }
                const title = document.getElementsByClassName("p-title-value")[0];
                if (title && games.includes(threadId(document.location))) {
                    title.insertBefore(createIcon(false), title.childNodes[title.childNodes.length - 1]);
                }
            }
            doUpdate();
            const latest = document.getElementById("latest-page_items-wrap");
            if (latest) {
                const observer = new MutationObserver(() => {
                    doUpdate();
                });
                observer.observe(latest, { attributes: true });
            }
        },
        args: [games]
    });
}
chrome.webNavigation.onCompleted.addListener((details) => {
    updateIcons(details.tabId);
}, { url: [{ hostSuffix: "f95zone.to" }] });


// Click on extension icon
chrome.action.onClicked.addListener(tab => {
    addGame(tab.url, tab.id);
});


// Context menus
chrome.runtime.onInstalled.addListener(async () => {
    chrome.contextMenus.create({
        id: `add-page-to-f95checker`,
        title: `Add this page to F95Checker`,
        contexts: ["page"],
        documentUrlPatterns: ["*://*.f95zone.to/threads/*"]
    });
    chrome.contextMenus.create({
        id: `add-link-to-f95checker`,
        title: `Add this link to F95Checker`,
        contexts: ["link"],
        targetUrlPatterns: ["*://*.f95zone.to/threads/*"]
    });
});
chrome.contextMenus.onClicked.addListener((info, tab) => {
    addGame(info.linkUrl || info.pageUrl, tab.id);
});


// Get game list every 5 minutes
setInterval(getGames, 5 * 60 * 1000);
getGames();
