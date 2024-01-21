// Qt WebEngine doesn't support extensions, only injecting basic JavaScript
// This script is therefore a plain js script that doesn't use chrome APIs
// This method however requires injecting into every single webpage
// That can be hit or miss and injecting into the same page twice can happen
// For this reason all top-level const's and let's have been removed to avoid SyntaxError's
// Also now this script doesn't do anything on its own, it only defines the functions
// It is up to the WebView to invoke them when appropriate

var games = [];

var sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

var rpcCall = async (method, path, body) => {
    try {
        const res = await (new Promise((resolve) => {
            new QWebChannel(qt.webChannelTransport, (channel) => {
                channel.objects.rpcproxy.handle(method, path, body, (ret) => {
                    resolve(new Response(ret.body, ret));
                });
            });
        }));
        if (!res.ok) {
            throw res.status;
        }
        return res;
    } catch {}
};

var getData = async () => {
    let res = null;

    res = await rpcCall('GET', '/games');
    games = res ? await res.json() : [];
};

var addGame = async (url) => {
    await rpcCall('POST', '/games/add', JSON.stringify([url]));
    await sleep(0.5 * 1000);
    await updateIcons();
};

// Add icons for games, reminders, etc.
var updateIcons = async () => {
    await getData();
    const extractThreadId = (url) => {
        const match = /threads\/(?:(?:[^\.\/]*)\.)?(\d+)/.exec(url);
        return match ? parseInt(match[1]) : null;
    };
    const createContainer = () => {
        const c = document.createElement('div');
        c.classList.add('f95checker-library-icons');
        c.style.display = 'inline';
        c.style.marginInlineEnd = '4px';
        return c;
    };
    const gamesIcon = () => {
        const icon = document.createElement('i');
        icon.style.fontFamily = "'Font Awesome 5 Pro'";
        icon.style.fontSize = '120%';
        icon.style.position = 'relative';
        icon.style.verticalAlign = 'bottom';
        icon.classList.add('fa', 'fa-heart-square');
        icon.setAttribute('title', 'This game is present in your F95Checker library!');
        icon.addEventListener('click', () =>
            alert('This game is present in your F95Checker library!')
        );
        icon.style.color = '#FD5555';
        return icon;
    };
    const removeOldIcons = () => {
        document.querySelectorAll('.f95checker-library-icons').forEach((e) => e.remove());
    };
    const addHrefIcons = () => {
        for (const elem of document.querySelectorAll('a[href*="/threads/"]')) {
            const id = extractThreadId(elem.href);

            if (!id || ![...games].includes(id)) {
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
            if (games.includes(id)) container.prepend(gamesIcon());

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
                    lastWhitespace = whitespaces[whitespaces.length - 1];
                    lastWhitespace.insertAdjacentElement('afterend', container);
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
            if (games.includes(id)) container.prepend(gamesIcon());
            if (container.firstChild)
                title.insertBefore(container, title.childNodes[title.childNodes.length - 1]);
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
};
