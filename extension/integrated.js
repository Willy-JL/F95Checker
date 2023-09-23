// Qt WebEngine doesn't support extensions, only injecting basic JavaScript
// This script is therefore a plain js script that doesn't use chrome APIs
// This method however requires injecting into every single webpage
// That can be hit or miss and injecting into the same page twice can happen
// For this reason all top-level const's and let's have been removed to avoid SyntaxError's
// Also now this script doesn't do anything on its own, it only defines the functions
// It is up to the WebView to invoke them when appropriate

rpcPort = 57096;
rpcURL = `http://localhost:${rpcPort}`;
settings = {};
games = [];
tags = {};

sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

rpcCall = async (method, path, body) => {
    try {
        const res = await fetch(`${rpcURL}${path}`, {
            method: method,
            body: body,
        });
        if (!res.ok) {
            throw res.status;
        }
        return res;
    } catch {}
};

getData = async () => {
    let res = null;

    res = await rpcCall('GET', '/settings');
    settings = res ? await res.json() : { ext_highlight_tags: false };

    res = await rpcCall('GET', '/games');
    games = res ? await res.json() : [];

    res = await rpcCall('GET', '/tags');
    tags = res ? await res.json() : { positive: [], negative: [], critical: [] };
};

addGame = async (url) => {
    await rpcCall('POST', '/games/add', JSON.stringify([url]));
    await sleep(0.5 * 1000);
    await render();
};

addReminder = async (url) => {
    await rpcCall('POST', '/reminders/add', JSON.stringify([url]));
    await sleep(0.5 * 1000);
    await render();
};

// Add icons for games, reminders, etc.
render = async () => {
    await getData();
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
        icon.style.position = 'relative';
        icon.style.verticalAlign = 'bottom';
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
        const title = document.getElementsByClassName('p-title-value')[0];
        if (title) {
            if (games.map((g) => g.id).includes(id)) container.prepend(gameIcon(id));
            if (container.firstChild)
                title.insertBefore(container, title.childNodes[title.childNodes.length - 1]);
        }
    };
    const processTags = () => {
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
        const tiles = document.querySelectorAll('div.resource-tile_body');
        tiles.forEach((tile) => {
            const observer = new MutationObserver(processTags);
            observer.observe(tile, { attributes: true, subtree: true });
        });
    };
    installMutationObservers();
    doUpdate();
};
