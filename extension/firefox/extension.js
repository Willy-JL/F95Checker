const rpcPort = 57096;
const rpcURL = `http://localhost:${rpcPort}`;
let games = [];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const rpcCall = async (method, path, body, tabId) => {
    try {
        const res = await fetch(`${rpcURL}${path}`, {
            method: method,
            body: body,
        });
        if (!res.ok) {
            throw res.status;
        }
        return res;
    } catch {
        if (tabId) {
            chrome.scripting.executeScript({
                target: { tabId: tabId },
                func: () => {
                    alert(
                        'Could not connect to F95CheckerX!\nIs it open and updated? Is RPC enabled?'
                    );
                },
            });
        }
    }
};

const getData = async () => {
    let res = null;

    res = await rpcCall('GET', '/games');
    games = res ? await res.json() : [];
};

const addGame = async (url, tabId) => {
    await rpcCall('POST', '/games/add', JSON.stringify([url]), tabId);
    await sleep(0.5 * 1000);
    await updateIcons(tabId);
};

// Add icons for games, reminders, etc.
const updateIcons = async (tabId) => {
    await getData();
    chrome.scripting.executeScript({
        target: { tabId: tabId },
        func: (games) => {
            const extractThreadId = (url) => {
                const match = /threads\/(?:(?:[^\.\/]*)\.)?(\d+)/.exec(url);
                return match ? parseInt(match[1]) : null;
            };
            const createContainer = () => {
                const c = document.createElement('div');
                c.classList.add('f95checkerx-library-icons');
                c.style.display = 'inline-flex';
                c.style.gap = '5px';
                c.style.padding = '3px 3px';
                return c;
            };
            const gameIcon = (id) => {
                const icon = document.createElement('i');
                icon.style.fontFamily = "'Font Awesome 5 Pro'";
                const game = games.find((g) => g.id === id);
                let full_text = '';
                if (game.reminder) {
                    icon.style.color = '#55eecc';
                    icon.classList.add('fa', 'fa-exclamation-square');
                    full_text = "You've marked this thread as a reminder";
                } else {
                    icon.style.color = '#FD5555';
                    icon.classList.add('fa', 'fa-heart-square');
                    full_text = 'This game is present in your library';
                }
                if (game.notes !== '') {
                    full_text += `\nNOTES:\n${game.notes}`;
                    icon.classList.replace('fa-heart-square', 'fa-pen-square');
                    icon.classList.replace('fa-exclamation-square', 'fa-pen-square');
                } else {
                }
                icon.setAttribute('title', full_text);
                icon.addEventListener('click', () => alert(full_text));
                return icon;
            };
            const removeOldIcons = () => {
                document.querySelectorAll('.f95checkerx-library-icons').forEach((e) => e.remove());
            };
            const addHrefIcons = () => {
                for (elem of document.querySelectorAll('a[href*="/threads/"]')) {
                    const id = extractThreadId(elem.href);

                    if (!id || ![...games.map((g) => g.id)].includes(id)) {
                        continue;
                    }

                    const isImage =
                        elem.classList.contains('resource-tile_link') ||
                        elem.parentNode.parentNode.classList.contains('es-slides');

                    if (
                        !isImage &&
                        (/page-.*$/.test(elem.href) ||
                            /post-\d*$/.test(elem.href) ||
                            /reply\?.*$/.test(elem.href) ||
                            elem.parentNode.classList.contains('pageNav') ||
                            elem.parentNode.classList.contains('pageNav-page'))
                    ) {
                        continue;
                    }

                    const container = createContainer();
                    if (games.map((g) => g.id).includes(id)) container.prepend(gameIcon(id));

                    if (isImage) {
                        container.style.position = 'absolute';
                        container.style.zIndex = '50';
                        container.style.right = '5px';
                        container.style.top = '5px';
                        container.style.background = '#262626';
                        container.style.border = 'solid #262626';
                        container.style.borderRadius = '4px';
                        container.style.fontSize = 'larger';
                    }

                    if (!isImage && elem.children.length > 0) {
                        // Search page
                        try {
                            whitespaces = elem.querySelectorAll('span.label-append');
                            whitespaces[whitespaces.length - 1].insertAdjacentElement(
                                'afterend',
                                container
                            );
                        } catch (e) {
                            continue;
                        }
                    } else if (elem.classList.contains('resource-tile_link')) {
                        // To accomodate all tile layouts on latest updates page
                        thumb = elem.querySelector('div.resource-tile_thumb');
                        thumb.insertAdjacentElement('beforebegin', container);
                    } else {
                        // Everywhere else
                        elem.insertAdjacentElement('beforebegin', container);
                    }
                }
            };
            const addPageIcon = () => {
                const id = extractThreadId(document.location);
                const container = createContainer();
                container.style.marginInlineEnd = '6px';
                const title = document.getElementsByClassName('p-title-value')[0];
                if (title) {
                    if (games.map((g) => g.id).includes(id)) container.prepend(gameIcon(id));
                    if (container.firstChild)
                        title.insertBefore(
                            container,
                            title.childNodes[title.childNodes.length - 1]
                        );
                }
            };
            const doUpdate = () => {
                removeOldIcons();
                addHrefIcons();
                addPageIcon();
            };
            const installMutationObservers = () => {
                const latest = document.getElementById('latest-page_items-wrap');
                if (latest) {
                    const observer = new MutationObserver(doUpdate);
                    observer.observe(latest, { attributes: true });
                }
            };
            installMutationObservers();
            doUpdate();
        },
        args: [games],
    });
};

chrome.webNavigation.onCompleted.addListener(
    (details) => {
        updateIcons(details.tabId);
    },
    { url: [{ hostSuffix: 'f95zone.to' }] }
);

// Click on extension icon
chrome.browserAction.onClicked.addListener((tab) => {
    addGame(tab.url, tab.id);
});

// Context menus
chrome.runtime.onInstalled.addListener(async () => {
    chrome.contextMenus.create({
        id: `add-page-to-f95checkerx`,
        title: `Add this page to F95CheckerX`,
        contexts: ['page'],
        documentUrlPatterns: ['*://*.f95zone.to/threads/*'],
    });
    chrome.contextMenus.create({
        id: `add-link-to-f95checkerx`,
        title: `Add this link to F95CheckerX`,
        contexts: ['link'],
        targetUrlPatterns: ['*://*.f95zone.to/threads/*'],
    });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
    switch (info.menuItemId) {
        case 'add-link-to-f95checkerx':
        case 'add-page-to-f95checkerx':
            addGame(info.linkUrl || info.pageUrl, tab.id);
            break;
    }
});

setInterval(getData, 5 * 60 * 1000); // 5 minutes
getData();
