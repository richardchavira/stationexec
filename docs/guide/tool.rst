Tool Use and Development
========================
A tool can be any sort of data source or sink. This could
be anything from a serial device to a custom software application to a
database to a web application. Each folder inside 'tool' defines a distinct tool and how to interact
with the tool.

A tool object inherits from `stationexec.toolbox.tool` and implements the
basic interaction methods. Beyond these few methods, the tool object provides
the methodology to interact with the tool of choice. View the example tool
(stationexec/built_in/example) to see how this is done. The 'station' definition
contains a tool manifest (tool_manifest.json) that defines which tools will be
loaded and which parameters will be provided to configure the tool. The
`toolbox <stationexec.toolbox.toolbox`> loads all tool objects, maintains connections,
provides status monitoring, and provides access to the tools upon request.

Create a Tool
-------------
Start by making a copy of the 'tool_template' folder inside of 'stationexec/templates'
into the workspace of your choice inside a parent level tool folder. The folder structure
should resemble the one below:

**Tool Folder Structure**

- Parent Tool Folder
    - tool_template - Folder
        - __init__.py - Required; empty
        - tool_template.py - Required
        - tool_handler_template.py - Optional
        - ui
            - custom_tool_ui.html - Optional
            - tool_template_control.html - Required
- __init__.py - Required; empty

This layout represents a tool of type 'tool_template'. Change the names of things to
represent the tool that you are developing. For an example tool called Special Robot,
the names would be changed as follows:

* 'tool_template' folder becomes 'special_robot'
* 'tool_template.py' becomes 'special_robot.py'
    * 'class ToolTemplate' inside of the file becomes 'class SpecialRobot'
* 'ui/tool_template_control.html' becomes 'ui/special_robot_control.html'

'tool_handler_template.py', 'class ToolHandlerTemplate' inside the file, and
'ui/custom_tool_ui.html' are both optional and do not have controlled names so
they can be changed or removed as desired. If making edits to the handlers, be
sure to adjust the import path at the top of the main tool .py file to account
for the name changes. This should also be adjusted from the default to account
for the new folder as it is no longer inside the stationexec package.

Programming
^^^^^^^^^^^
All tools must ultimately inherit from the `Tool <stationexec.toolbox.tool.Tool>` base class.
The `Tool <stationexec.toolbox.tool.Tool>` class provides underlying functionality to plug
your tool into the StationExec framework and also to aid in common tasks. There are a few required
methods to implement when developing a tool. They may not all be required for the particular tool, and
so may be empty (`pass`), but they must exist. These are the bare minimum of methods required for
a tool. Any other methods for operation can be added alongside these existing and will all be available
for use in normal operation (see `Setup and Use Tool` below).

**__init__**

Setup and store class member variables. The available arguments come from the 'configurations'
list in the tool_manifest file for the station. Must call the `super` method with \**kwargs to
setup the base tool.

**initialize**

Perform all actions required to set device up completely for use. After this method is called,
the tool is considered ready to use. Recommended to call 'self.set_online' or 'self.set_offline' with the outcome of
the initialization. If the initialization fails the driver should be written to allow execution
to continue. `verify_status` below should be able to detect and recover from the failure,
assuming the failure is due to external issues like a faulty cable or network connection
and can be recovered from.

**verify_status**

Periodically called (default 5 seconds) to determine if tool is online and healthy.
Use as a space to fix the tool if things have gone awry.

**shutdown**

Close all open connections and cleanup all resources. Called when program is shutting down.

**reset**

Reboot a malfunctioning tool.

**on_ui_command**

Called when a POST is received at '/tool/command' (see `API Endpoints` for more details)
targeted at this tool. This method should map the incoming 'command' argument and \**kwargs
to a tool method. See `Control UI` below for more details.

Tool Status
"""""""""""
If the connection or health status of the tool ever changes, call 'self.set_online' or 'self.set_offline' to let
the system know::

    # Set the tool status to online
    self.set_online()

    # Set the tool status to offline
    self.set_offline

Tool Utility
^^^^^^^^^^^^
The ToolUtil class is intended to make development and debugging of tools in a context similar
to deployment much simpler. The example below explains how to use the functionality to work
with your tool. Add this code to the bottom of your main tool file and run the file to use.

 **Example**::

    if __name__ == "__main__":
        from stationexec.toolbox.tool_util import ToolUtil

        # Instantiate the ToolUtil object
        tu = ToolUtil()

        # Build the dictionary of configurations for the tool
        #  All 'key': 'value' pairs will be passed into the __init__
        #  of the tool to be used to setup the tool as needed.
        configurations = {
            # 'key': 'value',
        }

        # Build the correctly formatted dictionary to configure the tool completely
        #  with this call. Arguments are: tool_type, name, tool_id, configurations
        #  tool_type: name of the tool folder and file
        #  name: display name for the tool - the friendly name
        #  tool_id: the unique identifier that is used to reference the tool
        #  configurations: dict from above
        tool_config = tu.build_tool_dict('example', 'Example', 'example_tool', configurations)

        # Prepare the tool object - this call takes the tool object reference itself
        #  (in this case, the 'example' tool, so pass the class 'Example' in) and the
        #  tool_config prepared in the previous step.
        tu.tool_setup(Example, tool_config)

        # Commands are optional helpers that can call any tool function at some later point
        #  in the future. This is helpful if you want to debug a function without dealing with
        #  the web server or ui. The first argument is how many seconds to wait before invoking
        #  the call. The next is the function itself. Then any args, then keyword args. This list
        #  can be passed in to the tool_run function and all functions will be called on schedule.
        commands = [
            # tu.tool_command_build(5, tu.obj.function_to_call, arg1, arg2, kwarg1='abc'),
        ]

        # Start the tool running. Schedules all (if any) commands defined above to run at the
        #  appropriate times. Starts a server at the port requested (default port is 8888),
        #  and invokes the tool in a similar context to what it runs in during deployment. With
        #  the server, you can access the tool UI at localhost:<port> and use that to send commands
        #  to the tool. Duration is how many seconds the tool context runs for. This is useful to
        #  force a clean shutdown after a test and nice for non-UI debugging. Set to 0 for indefinite run.
        #  Navigate to localhost:<port>/shutdown to shutdown.
        tu.tool_run(commands, port=8888, duration=0)

Setup and Use a Tool
--------------------

Tool Manifest
^^^^^^^^^^^^^


Tool Usage
^^^^^^^^^^

**Control UI**

**Checkout**


Tool User Interfaces
--------------------

Control UI
^^^^^^^^^^
The HTML file in the UI folder of a tool that shares the name of the tool + _ui
will be automatically served when the URL '/tool/<tool_id>/ui' is visited

e.g. for a tool of type example_tool:

- example_tool - Folder
    - __init__.py
    - example_tool.py - Required
    - ui
        - example_tool_ui.html - Required

The tool is instantiated with the following arguments in the tool_manifest file::

    {
        "tool_type": "example_tool",
        "name": "Example Tool",
        "tool_id": "example_tool_1",
        "configurations": {}
    }

The web page described in 'example_tool_ui.html' will be served from '/tool/example_tool_1/ui'
The file must have the same name as the tool type + _ui.html or it will not be found.

Typically this page will be served in the main context of the StationExec user
interface, so the header and body tags are not required.

Every one of these default tool pages has access to the pretty name of the tool
and the id of the tool. In the HTML, insert **{{tool_name}}** where you would like the
pretty name of the tool to appear and **{{tool_id}}** where you would like the id to
appear when the page is rendered. To place in javascript, make sure to put quotes
around it if it should be treated as a string.

Tool commands are sent by buttons. All buttons on the page that will send commands to
the tool that spawned the page will have class="{{tool_id}}" so that the button directs
to the proper tool The 'id' of the button will be passed to the tool object as one of
the arguments for the 'on_ui_command' function. The tool will decide which method to execute
based on this argument.

To pass arguments with a command, create form input objects that have a class that is
the same name as the id of the button. So if a button performs 'action1' it will have
id="action1"; if there is a numeric input that should be sent with it, the input will
have class="action1".  It is recommended to wrap the button and any related argument
inputs inside of a <div> for clarity.

The scripts that load from "/static/js/" are mapped to the 'stationexec/ui/js' folder
in the stationexec package.

Custom UI and Handler
^^^^^^^^^^^^^^^^^^^^^
A custom HTML file can be added to the UI folder to serve any purpose that the developer
wishes for it. It is entirely optional and can be used to extend the capability of a tool
beyond the built-in UI. There are no requirements for the naming of the file - it will be
served from the tool handler (if one exists). The file must exist in the ui folder of the
tool it belongs to.

For example, in the case of the tool template folder, the ToolHandlerTemplate inside
tool_handler_template.py will have the following inside its 'get' method::

   self.render('custom_tool_ui.html')

This will show the web page described in this document on whichever URL endpoint
was defined in the tool 'get_endpoints' method.

As the primary default UI had tool pretty name and id available to it as **{{tool_name}}**
and **{{tool_id}}**, the handler can make any data available to this page as desired.

To pass in custom data to the rendering template engine, pass in named arguments to
the self.render as follows::

   self.render('custom_tool_ui.html', socket=8888, url='/amazing/thing', place='SkyMall)

Now in the HTML and javascript, the developer would be able to access these arguments
by name - **{{socket}}** **{{url}}** and **{{place}}** anywhere they are useful.


Provided Tool Types
-------------------
Async Tool
^^^^^^^^^^

Camera
^^^^^^
