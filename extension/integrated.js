// Qt WebEngine doesn't support extensions, only injecting basic JavaScript
// This script is therefore a plain js script that doesn't use chrome APIs
// This method however requires injecting into every single webpage
// That can be hit or miss and injecting into the same page twice can happen
// For this reason all top-level const's and let's have been removed to avoid SyntaxError's
// Also now this script doesn't do anything on its own, it only defines the functions
// It is up to the WebView to invoke them when appropriate

rpcPort = 57095;
rpcURL = `http://localhost:${rpcPort}`;
games = [];


sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));


rpcCall = async (method, path, body) => {
    try {
        const res = await fetch(`${rpcURL}${path}`, {
            method: method,
            body: body
        });
        if (!res.ok) {
            throw res.status;
        }
        return res;
    } catch {}
}


getGames = async () => {
    const res = await rpcCall("GET", "/games");
    games = res ? await res.json() : [];
}


addGame = async (url) => {
    await rpcCall("POST", "/games/add", JSON.stringify([url]));
    await sleep(0.5 * 1000)
    await updateIcons();
}


// Add library icons for added games
updateIcons = async () => {
    await getGames();
    const threadId = (url) => {
        const match = /threads\/(?:(?:[^\.\/]*)\.)?(\d+)/.exec(url);
        return match ? parseInt(match[1]) : null;
    }
    const createIcon = (isImage) => {
        const icon = document.createElement("i");
        icon.classList.add("fa", "fa-box-heart", "f95checker-library-icon");
        icon.style.fontFamily = "'Font Awesome 5 Pro'";
        icon.style.color = "#FD5555";
        if (isImage) {
            icon.style.position = "absolute";
            icon.style.zIndex = "50";
            icon.style.right = "5px";
            icon.style.top = "5px";
            icon.style.fontSize = "larger";
            icon.style.background = "#262626";
            icon.style.border = "solid #262626";
            icon.style.borderWidth = "4px 5px";
            icon.style.borderRadius = "4px";
        } else {
            icon.style.marginRight = "0.2em"
        }
        icon.setAttribute("title", "This game is present in your F95Checker library!");
        icon.addEventListener("click", () => {
            alert("This game is present in your F95Checker library!");
        });
        return icon;
    }
    const doUpdate = () => {
        for (elem of document.getElementsByClassName("f95checker-library-icon")) {
            elem.style.display = "none";
            elem.innerHTML = "";
            elem.outerHTML = "";
            elem.remove();
        }
        let done = [];
        for (elem of document.querySelectorAll('a[href*="/threads/"]')) {
            const id = threadId(elem.href);
            if (!id || !games.includes(id)) {
                continue;
            }
            let isDone = false;
            for (doneElem of done) {
                if (doneElem.contains(elem)) {
                    isDone = true;
                    break;
                }
            }
            if (isDone) {
                continue;
            }
            const isImage = elem.classList.contains("resource-tile_link") || elem.parentNode.parentNode.classList.contains("es-slides");
            if (!isImage && !elem.href.endsWith("/unread")) {
                continue;
            }
            done.push(elem.parentNode);
            elem.insertAdjacentElement("beforebegin", createIcon(isImage));
        }
        const title = document.getElementsByClassName("p-title-value")[0];
        if (title && games.includes(threadId(document.location))) {
            title.insertBefore(createIcon(false), title.childNodes[title.childNodes.length - 1]);
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
}
