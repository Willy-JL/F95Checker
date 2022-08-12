// XML conversion utils
function objectToXml(object) {
    if (object instanceof Array || Object.keys(object).length !== 1) {
        throw 'variable has to be an object with a single property'
    }
    return variableToXml(object)
}
function variableToXml(variable, arrayItemPropertyName = null) {
    if (Array.isArray(variable)) {
        return variable.reduce((xml, propertyValue) => {
            const value = variableToXml(propertyValue)
            return `${xml}<${arrayItemPropertyName}>${value}</${arrayItemPropertyName}>`
        }, '')
    }
    if (variable instanceof Object) {
        return Object.entries(variable).reduce((xml, [propertyName, propertyValue]) => {
            const value = variableToXml(propertyValue, propertyName )
            const tag = propertyValue instanceof Array ? value : `<${propertyName}>${value}</${propertyName}>`
            return `${xml}${tag}`
        }, '')
    }
    return variable
}


// Actual logic
function addToF95Checker(url) {
    match = /threads\/(?:[^\/]*\.)?\d+/.exec(url)
    if (!match) {
        return
    }
    fetch("http://localhost:57095/", {
        method: "POST",
        body: objectToXml({
            methodCall: {
                methodName: "add_game",
                params: {
                    param: [
                        {
                            value: {
                                string: match[0]
                            }
                        }
                    ]
                }
            }
        })
    })
}


// Click on extension icon
chrome.browserAction.onClicked.addListener(tab => {
    addToF95Checker(tab.url)
})


// Context menus
chrome.runtime.onInstalled.addListener(async () => {
    chrome.contextMenus.create({
        id: `add-page-to-f95checker`,
        title: `Add this page to F95Checker`,
        contexts: ["page"],
        documentUrlPatterns: ["*://*.f95zone.to/threads/*"]
    })
    chrome.contextMenus.create({
        id: `add-link-to-f95checker`,
        title: `Add this link to F95Checker`,
        contexts: ["link"],
        targetUrlPatterns: ["*://*.f95zone.to/threads/*"]
    })
})
chrome.contextMenus.onClicked.addListener((info, tab) => {
    addToF95Checker(info.linkUrl || info.pageUrl)
})
