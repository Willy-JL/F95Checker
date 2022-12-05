const rpcPort = 57095;
const rpcURL = `http://localhost:${rpcPort}`;


function addToF95Checker(url) {
    match = /threads\/(?:[^\/]*\.)?\d+/.exec(url);
    if (!match) {
        return;
    }
    fetch(`${rpcURL}/games/add`, {
        method: "POST",
        body: JSON.stringify([url])
    });
}


// Click on extension icon
chrome.browserAction.onClicked.addListener(tab => {
    addToF95Checker(tab.url);
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
    addToF95Checker(info.linkUrl || info.pageUrl);
});
