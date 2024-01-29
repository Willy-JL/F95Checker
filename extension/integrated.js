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
    if(typeof method !== 'string' || typeof path !== 'string' || (typeof body !== 'string' && body !== null)) {
        return {};
    }
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
    const res = await rpcCall('GET', '/games', null);
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
    const injectCustomWebfont = () => {
        const styleTag = document.createElement('style');
        const font_url = chrome.runtime.getURL('materialdesignicons-webfont.ttf'); // FIXME
        const cssContent = String.raw`
            @font-face{
                font-family: "MDI Custom";
                src: url('${font_url}') format('truetype');
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
                container.style.right = '5px';
                container.style.top = '5px';
                container.style.background = '#262626';
                container.style.border = 'solid #262626';
                container.style.borderRadius = '4px';
                container.style.fontSize = '1.5em';
                container.style.boxShadow = `0px 0px 30px 30px ${color.slice(0, 7)}bb`;
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
    const doUpdate = () => {
        injectCustomWebfont();
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
