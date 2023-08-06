const rpcPort = 57095;
const rpcURL = `http://localhost:${rpcPort}`;
let games = [];
let bookmarks = [];


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


const getData = async () => {
    let res = null;

    res = await rpcCall("GET", "/games");
    games = res ? await res.json() : [];

    res = await rpcCall("GET", "/bookmarks");
    bookmarks = res ? await res.json() : [];
}


const addGame = async (url, tabId) => {
    await rpcCall("POST", "/games/add", JSON.stringify([url]), tabId);
    await sleep(0.5 * 1000)
    await updateIcons(tabId);
}


const addBookmark = async (url, tabId) => {
    await rpcCall("POST", "/bookmarks/add", JSON.stringify([url]), tabId);
    await sleep(0.5 * 1000)
    await updateIcons(tabId);
}


// Add icons for games and bookmarks
const updateIcons = async (tabId) => {
    await getData();
    chrome.scripting.executeScript({
        target: { tabId: tabId },
        func: (games, bookmarks) => {
            const threadId = (url) => {
                const match = /threads\/(?:(?:[^\.\/]*)\.)?(\d+)/.exec(url);
                return match ? parseInt(match[1]) : null;
            }
            const createContainer = () => {
                const c = document.createElement("div");
                c.classList.add("f95checker-library-icons");
                c.style.display = "inline-flex";
                c.style.gap = "5px";
                c.style.padding = "3px 3px";
                return c;
            }
            const gamesIcon = () => {
                const icon = document.createElement("i");
                icon.style.fontFamily = "'Font Awesome 5 Pro'";
                icon.classList.add("fa", "fa-box-heart");
                icon.setAttribute("title", "This game is present in your F95Checker library!");
                icon.addEventListener("click", () => alert("This game is present in your F95Checker library!"));
                icon.style.color = "#FD5555";
                return icon;
            }
            const bookmarksIcon = () => {
                const icon = document.createElement("i");
                icon.style.fontFamily = "'Font Awesome 5 Pro'";
                icon.classList.add("fa", "fa-sticky-note");
                icon.setAttribute("title", "Thread bookmarked");
                icon.addEventListener("click", () => alert("Thread bookmarked"));
                icon.style.color = "#55eecc";
                return icon;
            }
            const doUpdate = () => {
                document.querySelectorAll('.f95checker-library-icons').forEach(e => e.remove());
                for (elem of document.querySelectorAll('a[href*="/threads/"]')) {
                    const id = threadId(elem.href);
                    const container = createContainer();
                    if (!id || ![...games, ...bookmarks].includes(id)) {
                        continue;
                    }
                    const isImage = elem.classList.contains("resource-tile_link") || elem.parentNode.parentNode.classList.contains("es-slides");
                    if (!isImage && !elem.href.endsWith("/unread")) {
                        continue;
                    }
                    if (isImage) {
                        container.style.position = "absolute";
                        container.style.zIndex = "50";
                        container.style.right = "5px";
                        container.style.top = "5px";
                        container.style.background = "#262626";
                        container.style.border = "solid #262626";
                        container.style.borderRadius = "4px";
                        container.style.fontSize = "larger";
                    }
                    if (games.includes(id)) container.prepend(gamesIcon());
                    if (bookmarks.includes(id)) container.prepend(bookmarksIcon());
                    elem.insertAdjacentElement("beforebegin", container);
                }
                const id = threadId(document.location);
                const container = createContainer();
                container.style.marginInlineEnd = "6px";
                const title = document.getElementsByClassName("p-title-value")[0];
                if (title) {
                    if (games.includes(id)) container.prepend(gamesIcon());
                    if (bookmarks.includes(id)) container.prepend(bookmarksIcon());
                    if (container.firstChild) title.insertBefore(container, title.childNodes[title.childNodes.length - 1]);
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
        args: [games, bookmarks]
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
    chrome.contextMenus.create({
        id: `add-page-to-bookmarks`,
        title: `Add this page to bookmarks`,
        contexts: ["page"],
        documentUrlPatterns: ["*://*.f95zone.to/threads/*"]
    });
    chrome.contextMenus.create({
        id: `add-link-to-bookmarks`,
        title: `Add this link to bookmarks`,
        contexts: ["link"],
        targetUrlPatterns: ["*://*.f95zone.to/threads/*"]
    });
});
chrome.contextMenus.onClicked.addListener((info, tab) => {
    switch (info.menuItemId) {
        case 'add-link-to-f95checker':
        case 'add-page-to-f95checker':
            addGame(info.linkUrl || info.pageUrl, tab.id);
            break;
        case 'add-link-to-bookmarks':
        case 'add-page-to-bookmarks':
            addBookmark(info.linkUrl || info.pageUrl, tab.id);
            break;
    }
});


// Get data every 5 minutes
setInterval(getData, 5 * 60 * 1000);
getData();
