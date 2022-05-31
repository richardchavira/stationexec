function htmlParseOptions(saveScriptTag, buttonCallback) {
    let supportedSyntheticEvents = ["onClick", "onChange", "onFocus", "onBlur", "onInput", "onSubmit", "onDoubleClick",
        "onDrag", "onDragEnd", "onDragEnter", "onDragExit", "onDragLeave", "onDragOver", "onDragStart", "onDrop",
        "onMouseDown", "onMouseEnter", "onMouseLeave", "onMouseMove", "onMouseOut", "onMouseOver", "onMouseUp",
        "onSelect", "onScroll", "onLoad", "onToggle", "onCopy", "onCut", "onPaste", "onKeyDown", "onKeyPress",
        "onKeyUp"];
    let supportedEvents = supportedSyntheticEvents.map(e => e.toLowerCase());

    return ({
        // Options for how to parse the incoming HTML from the station
        // https://github.com/remarkablemark/html-react-parser
        replace: (domNode) => {
            if (!domNode) return;
            if (domNode.attribs) {
                for (let key in domNode.attribs) {
                    // If object has an event tied to it, take the javascript from the event
                    // and wrap it in a new function with a generated name, put that function in a new
                    // <script> tag in the header, and set the React synthetic event to be the new
                    // function. The <script> tag will be removed in componentWillUnmount
                    //
                    // Supported synthetic events are in array at top
                    //
                    // e.g. from a <input type="checkbox"... definition:
                    //   onclick("document.getElementById('to-hide').hidden = !this.checked")
                    // requires a change to be more explicit as 'this' will no longer mean anything:
                    //   onclick(""document.getElementById('to-hide').hidden = !document.getElementById
                    //           ('box-hider').checked")
                    // is transformed by this script into:
                    // <header>
                    //     ...
                    //     <script id=onclick_tag_123ab>
                    //         function onclick_tag_123ab() {
                    //             document.getElementById('item').hidden = !document.getElementById
                    //                  ('box-hider').checked")
                    //         }
                    //     </script>
                    // </header
                    if (supportedEvents.includes(key)) {
                        let script = document.createElement("script");
                        script.id = random_id(key + "_tag", length = 5);
                        saveScriptTag(script.id);
                        script.text = "function " + script.id + "() { " + domNode.attribs[key] + " }";
                        document.head.appendChild(script);
                        delete domNode.attribs[key];
                        let index = supportedEvents.indexOf(key);
                        domNode.attribs[supportedSyntheticEvents[index]] = window[script.id]
                    }
                }
                if (domNode.attribs.value) {
                    // Convert "value" attribute to React friendly "defaultValue" to prevent inputs from
                    // becoming read-only
                    domNode.attribs.defaultValue = domNode.attribs.value;
                    delete domNode.attribs.value
                }
            }
            if (domNode.type === "script") {
                // Split off an in-lined <script> tag and append it to the head of the document
                // so that it will be usable. The <script> tag will be removed in
                // componentWillUnmount
                let script = document.createElement("script");
                if(domNode.attribs.src)
                    script.src = domNode.attribs.src;
                script.id = random_id("script_tag", length=5);
                saveScriptTag(script.id);
                if (domNode.children[0])
                    script.text = domNode.children[0].data;
                document.head.appendChild(script);
                return React.createElement(React.Fragment)
            } else if ((domNode.name === "button") || (domNode.name === "input" && domNode.attribs.type === "button" )){
                if (domNode.attribs.onClick) {
                    // If the react onClick event already exists for this button, it must have had a
                    // onclick event defined and processed above. Set the onClick event to now
                    // trigger both the previously defined function and the standard on_button event
                    let fn1 = domNode.attribs.onClick;
                    domNode.attribs.onClick = (evt) => { fn1(evt); buttonCallback(evt) }
                } else {
                    // Add button press listener
                    domNode.attribs.onClick = buttonCallback
                }
                domNode.attribs.class += " se-button";
            } else if (domNode.name === "iframe") {
                // In case any special processing on an iframe is required - TBD
            }
        }
    })
}
