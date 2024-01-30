const rpcPort = 57095;
const rpcURL = `http://127.0.0.1:${rpcPort}`;
let games = [];
let settings = {};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const rpcCall = async (method, path, body, tabId) => {
    if(typeof method !== 'string' || typeof path !== 'string' || (typeof body !== 'string' && body !== null)) {
        return {};
    }
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
                        'Could not connect to F95Checker!\nIs it open and updated? Is RPC enabled?'
                    );
                },
            });
        }
    }
};

const getData = async () => {
    let res;
    res = await rpcCall('GET', '/games', null);
    games = res ? await res.json() : [];
    res = await rpcCall('GET', '/settings', null);
    settings = res ? await res.json() : {
        "icon_glow": true,
        "highlight_tags": false,
        "tags_highlights": {},
    };
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
        func: (games, settings, rpcURL) => {
            const injectCustomWebfont = () => {
                const styleTag = document.createElement('style');
                const cssContent = String.raw`
                    @font-face{
                        font-family: "MDI Custom";
                        src: url('${rpcURL}/assets/mdi-webfont.ttf') format('truetype');
                        font-weight: normal;
                        font-style: normal;
                    }
                    .mdi:before {
                        display: inline-block;
                        font: normal normal normal 24px/1 "MDI Custom";
                        font-size: inherit;
                        text-rendering: auto;
                        line-height: inherit;
                        -webkit-font-smoothing: antialiased;
                        -moz-osx-font-smoothing: grayscale;
                    }
                    .mdi::before {
                        content: var(--mdi-i);
                    }
                `;
                styleTag.appendChild(document.createTextNode(cssContent));
                document.head.appendChild(styleTag);
            };
            const extractThreadId = (url) => {
                const match = /threads\/(?:(?:[^\.\/]*)\.)?(\d+)/.exec(url);
                return match ? parseInt(match[1]) : null;
            };
            const createContainer = () => {
                const c = document.createElement('div');
                c.classList.add('f95checker-library-icons');
                c.style.display = 'inline-block';
                return c;
            };
            const createIcon = (gameId) => {
                const icon = document.createElement('i');
                const game = games.find(g => g.id === gameId);
                icon.classList.add('mdi');
                icon.style.setProperty('--mdi-i', `'${game.icon}'`);
                icon.setAttribute('title', 'This game is present in your F95Checker library!');
                icon.addEventListener('click', () =>
                    alert('This game is present in your F95Checker library!')
                );
                icon.style.color = game.color;
                return [icon, game.color];
            };
            const createNbsp = () => {
                const span = document.createElement('span');
                span.style.display = 'inline-block';
                span.innerHTML = '&nbsp;';
                return span;
            };
            const removeOldIcons = () => {
                document.querySelectorAll('.f95checker-library-icons').forEach((e) => e.remove());
            };
            const addHrefIcons = () => {
                for (const elem of document.querySelectorAll('a[href*="/threads/"]')) {
                    const id = extractThreadId(elem.href);

                    if (!id || !games.map(g => g.id).includes(id)) {
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
                    const [icon, color] = createIcon(id);
                    container.prepend(icon);

                    if (isImage) {
                        container.style.position = 'absolute';
                        container.style.zIndex = '50';
                        container.style.left = '5px';
                        container.style.top = '5px';
                        container.style.width = '28px';
                        container.style.textAlign = 'center';
                        container.style.background = '#262626';
                        container.style.borderRadius = '4px';
                        container.style.fontSize = '1.5em';
                        if (settings.icon_glow) {
                            container.style.boxShadow = `0px 0px 30px 30px ${color.slice(0, 7)}bb`;
                        }
                    }

                    if (!isImage && elem.children.length > 0) {
                        // Search page
                        try {
                            container.style.fontSize = '1.2em';
                            container.style.verticalAlign = '-2px';
                            const whitespaces = elem.querySelectorAll('span.label-append');
                            const lastWhitespace = whitespaces[whitespaces.length - 1];
                            lastWhitespace.insertAdjacentElement('afterend', createNbsp());
                            lastWhitespace.insertAdjacentElement('afterend', container);
                        } catch (e) {
                            continue;
                        }
                    } else if (elem.classList.contains('resource-tile_link')) {
                        // To accomodate all tile layouts on latest updates page
                        const thumb = elem.querySelector('div.resource-tile_thumb');
                        thumb.insertAdjacentElement('beforebegin', container);
                    } else {
                        // Everywhere else
                        container.style.fontSize = '1.2em';
                        container.style.verticalAlign = '-2px';
                        elem.insertAdjacentElement('beforebegin', container);
                        elem.insertAdjacentElement('beforebegin', createNbsp());
                    }
                }
            };
            const addPageIcon = () => {
                const id = extractThreadId(document.location);
                const container = createContainer();
                container.style.fontSize = '1.3em';
                container.style.verticalAlign = '-3px';
                const title = document.getElementsByClassName('p-title-value')[0];
                if (title) {
                    if (games.map(g => g.id).includes(id)) {
                        const [icon, _] = createIcon(id);
                        container.prepend(icon);
                        title.insertBefore(
                            container,
                            title.childNodes[title.childNodes.length - 1]
                        );
                        title.insertBefore(
                            createNbsp(),
                            title.childNodes[title.childNodes.length - 1]
                        );
                    };
                }
            };
            const installHighlighterMutationObservers = () => {
                const tiles = document.querySelectorAll('div.resource-tile_body');
                tiles.forEach((tile) => {
                    const observer = new MutationObserver(highlightTags);
                    observer.observe(tile, { attributes: true, subtree: true });
                });
            }
            const highlightTags = () => {
                // Latest Updates
                const hoveredTiles = document.querySelectorAll('div.resource-tile-hover');
                hoveredTiles.forEach((tile) => {
                    const tagsWrapper = tile.querySelector('div.resource-tile_tags');
                    if (!tagsWrapper) return;
                    const tagSpans = tagsWrapper.querySelectorAll('span');
                    tagSpans.forEach((span) => {
                        const name = span.innerText;
                        if (settings.tags_highlights.hasOwnProperty(name)) {
                            const highlight = settings.tags_highlights[name];
                            span.style.color = highlightColors[highlight].text;
                            span.style.backgroundColor = highlightColors[highlight].background;
                            span.style.border = highlightColors[highlight].border;
                        }
                    });
                });
                // Thread
                const tagLinks = document.querySelectorAll('a.tagItem');
                tagLinks.forEach((link) => {
                    const name = link.innerText;
                    if (settings.tags_highlights.hasOwnProperty(name)) {
                        const highlight = settings.tags_highlights[name];
                        link.style.color = highlightColors[highlight].text;
                        link.style.backgroundColor = highlightColors[highlight].background;
                        link.style.border = highlightColors[highlight].border;
                    }
                });
            };
            const doUpdate = () => {
                injectCustomWebfont();
                removeOldIcons();
                addHrefIcons();
                addPageIcon();
                if (settings.highlight_tags) {
                    installHighlighterMutationObservers();
                    highlightTags();
                }
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
        args: [games, settings, rpcURL],
    });
};

chrome.webNavigation.onCompleted.addListener(
    (details) => {
        updateIcons(details.tabId);
    },
    { url: [{ hostSuffix: 'f95zone.to' }] }
);

// Click on extension icon
chrome.action.onClicked.addListener((tab) => {
    addGame(tab.url, tab.id);
});

// Context menus
chrome.runtime.onInstalled.addListener(async () => {
    chrome.contextMenus.create({
        id: `add-page-to-f95checker`,
        title: `Add this page to F95Checker`,
        contexts: ['page'],
        documentUrlPatterns: ['*://*.f95zone.to/threads/*'],
    });
    chrome.contextMenus.create({
        id: `add-link-to-f95checker`,
        title: `Add this link to F95Checker`,
        contexts: ['link'],
        targetUrlPatterns: ['*://*.f95zone.to/threads/*'],
    });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
    switch (info.menuItemId) {
        case 'add-link-to-f95checker':
        case 'add-page-to-f95checker':
            addGame(info.linkUrl || info.pageUrl, tab.id);
            break;
    }
});

setInterval(getData, 5 * 60 * 1000); // 5 minutes
getData();
