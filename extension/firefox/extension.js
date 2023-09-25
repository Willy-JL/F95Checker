const rpcPort = 57096;
const rpcURL = `http://localhost:${rpcPort}`;
let settings = {};
let games = [];
let tags = {};

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

    res = await rpcCall('GET', '/settings');
    settings = res ? await res.json() : { ext_highlight_tags: false };

    res = await rpcCall('GET', '/games');
    games = res ? await res.json() : [];

    res = await rpcCall('GET', '/tags');
    tags = res ? await res.json() : { positive: [], negative: [], critical: [] };
};

const addGame = async (url, tabId) => {
    await rpcCall('POST', '/games/add', JSON.stringify([url]), tabId);
    await sleep(0.5 * 1000);
    await render(tabId);
};

const addReminder = async (url, tabId) => {
    await rpcCall('POST', '/reminders/add', JSON.stringify([url]), tabId);
    await sleep(0.5 * 1000);
    await render(tabId);
};

const addFavorite = async (url, tabId) => {
    await rpcCall('POST', '/favorites/add', JSON.stringify([url]), tabId);
    await sleep(0.5 * 1000);
    await render(tabId);
};

const render = async (tabId) => {
    await getData();
    chrome.scripting.executeScript({
        target: { tabId: tabId },
        func: (settings, games, tags) => {
            const extractThreadId = (url) => {
                const match = /threads\/(?:(?:[^\.\/]*)\.)?(\d+)/.exec(url);
                return match ? parseInt(match[1]) : null;
            };
            const createContainer = () => {
                const c = document.createElement('div');
                c.classList.add('f95checkerx-library-icons');
                c.style.display = 'inline';
                c.style.marginInlineEnd = '4px';
                return c;
            };
            const gameIcon = (id) => {
                const icon = document.createElement('i');
                icon.style.fontFamily = "'Font Awesome 5 Pro'";
                icon.style.fontSize = '120%';
                icon.style.verticalAlign = 'bottom';
                const game = games.find((g) => g.id === id);
                let full_text = '';
                if (game.reminder) {
                    icon.style.color = '#55eecc';
                    icon.classList.add('fa', 'fa-exclamation-square');
                    full_text = "You've marked this thread as a reminder";
                } else if (game.favorite) {
                    icon.style.color = '#fcc808';
                    icon.classList.add('fa', 'fa-heart-square');
                    full_text = "You've marked this thread as a favorite";
                } else {
                    icon.style.color = '#FD5555';
                    icon.classList.add('fa', 'fa-check-square');
                    full_text = 'This game is present in your tracker';
                }
                if (game.notes !== '') {
                    full_text += `\nNOTES:\n${game.notes}`;
                    icon.classList.replace('fa-check-square', 'fa-pen-square');
                    icon.classList.replace('fa-heart-square', 'fa-pen-square');
                    icon.classList.replace('fa-exclamation-square', 'fa-pen-square');
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
            const highlightTags = () => {
                if (!settings.ext_highlight_tags) {
                    return;
                }
                // Latest Updates
                const hoveredTiles = document.querySelectorAll('div.resource-tile-hover');
                hoveredTiles.forEach((tile) => {
                    const tagsWrapper = tile.querySelector('div.resource-tile_tags');
                    if (!tagsWrapper) {
                        return;
                    }
                    const tagSpans = tagsWrapper.querySelectorAll('span');
                    tagSpans.forEach((span) => {
                        const name = span.innerHTML;
                        if (tags.positive.includes(name)) {
                            span.style.backgroundColor = '#006600';
                        } else if (tags.negative.includes(name)) {
                            span.style.backgroundColor = '#990000';
                        } else if (tags.critical.includes(name)) {
                            span.style.backgroundColor = '#000000';
                        }
                    });
                });
                // Thread page
                const tagLinks = document.querySelectorAll('a.tagItem');
                tagLinks.forEach((tag) => {
                    const name = tag.innerHTML;
                    if (tags.positive.includes(name)) {
                        tag.style.color = 'white';
                        tag.style.backgroundColor = '#006600';
                    } else if (tags.negative.includes(name)) {
                        tag.style.color = 'white';
                        tag.style.backgroundColor = '#990000';
                    } else if (tags.critical.includes(name)) {
                        tag.style.color = 'white';
                        tag.style.backgroundColor = '#000000';
                        tag.style.border = '1px solid #ffffff55';
                    }
                });
            };
            const processTags = () => {
                highlightTags();
                const tiles = document.querySelectorAll('div.resource-tile_body');
                tiles.forEach((tile) => {
                    const observer = new MutationObserver(highlightTags);
                    observer.observe(tile, { attributes: true, subtree: true });
                });
            };
            const doUpdate = () => {
                removeOldIcons();
                addHrefIcons();
                addPageIcon();
                processTags();
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
        args: [settings, games, tags],
    });
};

chrome.webNavigation.onCompleted.addListener(
    (details) => {
        render(details.tabId);
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
        title: `Add page to Tracker`,
        contexts: ['page'],
        documentUrlPatterns: ['*://*.f95zone.to/threads/*'],
    });
    chrome.contextMenus.create({
        id: `add-link-to-f95checkerx`,
        title: `Add link to Tracker`,
        contexts: ['link'],
        targetUrlPatterns: ['*://*.f95zone.to/threads/*'],
    });
    chrome.contextMenus.create({
        id: `add-page-to-f95checkerx-reminder`,
        title: `Add page to Reminders`,
        contexts: ['page'],
        documentUrlPatterns: ['*://*.f95zone.to/threads/*'],
    });
    chrome.contextMenus.create({
        id: `add-link-to-f95checkerx-reminder`,
        title: `Add link to Reminders`,
        contexts: ['link'],
        targetUrlPatterns: ['*://*.f95zone.to/threads/*'],
    });
    chrome.contextMenus.create({
        id: `add-page-to-f95checkerx-favorite`,
        title: `Add page to Favorites`,
        contexts: ['page'],
        documentUrlPatterns: ['*://*.f95zone.to/threads/*'],
    });
    chrome.contextMenus.create({
        id: `add-link-to-f95checkerx-favorite`,
        title: `Add link to Favorites`,
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
        case 'add-link-to-f95checkerx-reminder':
        case 'add-page-to-f95checkerx-reminder':
            addReminder(info.linkUrl || info.pageUrl, tab.id);
            break;
        case 'add-link-to-f95checkerx-favorite':
        case 'add-page-to-f95checkerx-favorite':
            addFavorite(info.linkUrl || info.pageUrl, tab.id);
            break;
    }
});

setInterval(getData, 5 * 60 * 1000); // 5 minutes
getData();
