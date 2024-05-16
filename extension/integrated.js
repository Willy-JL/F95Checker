// Qt WebEngine doesn't support extensions, only injecting basic JavaScript
// This script is therefore a plain js script that doesn't use chrome APIs
// This method however requires injecting into every single webpage
// That can be hit or miss and injecting into the same page twice can happen
// For this reason all top-level const's and let's have been removed to avoid SyntaxError's
// Also now this script doesn't do anything on its own, it only defines the functions
// It is up to the WebView to invoke them when appropriate

var games = [];
var settings = {};

var sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

var rpcCall = async (method, path, body) => {
    if(typeof method !== 'string' || typeof path !== 'string' || (typeof body !== 'string' && body !== null)) {
        return {};
    }
    try {
        const res = await (new Promise((resolve) => {
            new QWebChannel(qt.webChannelTransport, (channel) => {
                channel.objects.rpcproxy.handle(method, path, body, (ret) => {
                    resolve(new Response(atob(ret.body), ret));
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

var addGame = async (url) => {
    await rpcCall('POST', '/games/add', JSON.stringify([url]));
    await sleep(0.5 * 1000);
    await updateIcons();
};

// Add icons for games, reminders, etc.
var updateIcons = async () => {
    await getData();
    const font = await (await rpcCall('GET', '/assets/mdi-webfont.ttf', null)).text();
    const font_url = `data:@font/ttf;base64,${btoa(font)}`;
    const injectCustomWebfont = () => {
        const styleTag = document.createElement('style');
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
        tooltiptext = 'This game is present in your F95Checker library!';
        if (game.notes !== '') {
            tooltiptext += `\n\nNOTES: ${game.notes}`;
        }
        icon.setAttribute('title', tooltiptext);
        icon.addEventListener('click', () =>
            alert(tooltiptext)
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
    const isValidHrefElem = (elem, elemId, pageId) => {
        // Ignore Reply and Quote buttons
        if (/reply\?.*$/.test(elem.href)) return false;

        // Ignore post navigation
        const parent = elem.parentNode
        if (/page-.*$/.test(elem.href)) return false;
        if (parent && parent.classList.contains('pageNav')) return false;
        if (parent && parent.classList.contains('pageNav-page')) return false;

        // Ignore post numbers
        const ul = elem.closest('ul')
        if (ul && ul.classList.contains('message-attribution-opposite')) return false;
        // Ignore links in the OP pointing to the posts in the same thread
        if (elem.closest('.message-threadStarterPost') && elemId === pageId) return false;

        return true;
    }
    const addHrefIcons = () => {
        const pageId = extractThreadId(document.location)
        for (const elem of document.querySelectorAll('a[href*="/threads/"]')) {
            const elemId = extractThreadId(elem.href);

            if (!elemId || !games.map(g => g.id).includes(elemId)) {
                continue;
            }

            const isImage =
                elem.classList.contains('resource-tile_link') ||
                elem.parentNode.parentNode.classList.contains('es-slides');

            if (!isImage && !isValidHrefElem(elem, elemId, pageId)) {
                continue;
            }

            const container = createContainer();
            const [icon, color] = createIcon(elemId);
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
        const highlightColors = {
            1: {text: 'white', background: '#006600', border: '1px solid #ffffff55'}, // Positive
            2: {text: 'white', background: '#990000', border: '1px solid #ffffff55'}, // Negative
            3: {text: 'white', background: '#000000', border: '1px solid #ffffff55'}, // Critical
        };
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
};
