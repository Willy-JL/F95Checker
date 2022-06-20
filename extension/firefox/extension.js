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

chrome.browserAction.onClicked.addListener(tab => {
    fetch("http://localhost:57095/", {
        method: "POST",
        body: objectToXml({
            methodCall: {
                methodName: "add_game",
                params: {
                    param: [
                        {
                            value: {
                                string: /threads\/(?:[^\/]*\.)?\d+/.exec(tab.url)[0]
                            }
                        }
                    ]
                }
            }
        })
    });
});
