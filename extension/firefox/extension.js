const rpcPort = 57095;
const rpcURL = `http://localhost:${rpcPort}`;


async function rpcCall(tab, method, path, body) {
    try {
        const res = await fetch(`${rpcURL}${path}`, {
            method: method,
            body: body
        });
        if (!res.ok) {
            throw res.status;
        }
    } catch {
        chrome.scripting.executeScript({
            target: {tabId: tab.id},
            func: () => { alert("Could not connect to F95Checker!\nIs it open and updated? Is RPC enabled?") }
        });
    }
}


async function addGame(url, tab) {
    await rpcCall(tab, "POST", "/games/add", JSON.stringify([url]));
}


// Click on extension icon
chrome.browserAction.onClicked.addListener(tab => {
    addGame(tab.url, tab);
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
    addGame(info.linkUrl || info.pageUrl, tab);
});
