API Endpoints
=============
Primary functionality of stationexec is exposed via REST interfaces to allow for natural interaction
in a networked context. Stationexec can provide data and be controlled over these interfaces. An author can
also easily create new endpoints to extend functionality.

To Be Defined
^^^^^^^^^^^^^
- /login
- /logout
- /restart
- /config
- /settings

Endpoints
^^^^^^^^^

.. http:post:: /shutdown

    Shuts down stationexec

.. http:post:: /sequence/start

    Starts the sequence

.. http:post:: /sequence/stop

    Requests a stop to the running sequence

.. http:get:: /sequence/status

    Returns JSON describing the status of each operation in the sequence

    **Example Request (jquery)**:

    ::

        $.ajax({
            url: "/sequence/status",
            dataType: 'json',
            context: this,
            complete: function (resp) {
                var data = resp.responseJSON;
        }});

    **Example Response**:

    ::

        [
          {
            "active": true,
            "sequence_id": 4,
            "stop": false,
            "shutdown": false
          },
          {
            "status": 0,
            "description": "Submit image for processing",
            "order": 2,
            "priority": 5,
            "operation_name": "Process Image",
            "id": "ProcessImage"
          },
          {
            "status": 1,
            "description": "Return the string",
            "order": 1,
            "priority": 5,
            "operation_name": "Print There",
            "id": "There"
          }
        ]

    :query None: None
    :reqheader Authorization: Authentication Required
    :resheader Content-Type: content/json
    :statuscode 200: no error


.. http:get:: /tool

    Returns JSON describing available endpoints for tool user interfaces

    **Example Request (jquery)**:

    ::

        $.ajax({
            url: "/tool",
            dataType: 'json',
            context: this,
            complete: function (resp) {
                var data = resp.responseJSON;
        }});

    **Example Response**:

    ::

        {
          "example_tool": {
            "ui": "/tool/ui/example_tool",
            "name": "Example",
            "cal": "/tool/cal/example_tool"
          },
          "example2_tool": {
            "ui": "/tool/ui/example2_tool",
            "name": "Example 2",
            "cal": "/tool/cal/example2_tool"
          }
        }

    :query None: None
    :resheader Content-Type: content/json
    :statuscode 200: no error


.. http:get:: /tool/status

    Returns JSON describing online/offline and status message for each connected tool

    **Example Request (jquery)**:

    ::

        $.ajax({
            url: "/tool/status",
            dataType: 'json',
            context: this,
            complete: function (resp) {
                var data = resp.responseJSON;
        }});

    **Example Response**:

    ::

        [
          {
            "status": "Offline",
            "tool_id": "example_tool",
            "tool_type": "example",
            "name": "Example",
            "inuse": false,
            "status_bool": false,
            "details": "Tool is offline"
          },
          {
            "status": "Online",
            "tool_id": "example2_tool",
            "tool_type": "example2",
            "name": "Example 2",
            "inuse": false,
            "status_bool": true,
            "details": "Tool is online"
          }
        ]

    :query None: None
    :resheader Content-Type: content/json
    :statuscode 200: no error


.. http:post:: /tool/command

    Post JSON to this endpoint to perform an action with a tool

    **Example Request (jquery)**:

    ::

        $.ajax({
            url: "/tool/command",
            headers: {'Content-Type':'application/json'},
            method: 'POST',
            dataType: 'json',
            data: JSON.stringify(command),
        });

    :query command: JSON argument below
    :statuscode 200: no error

    JSON 'command' argument::


        {
          target: <tool_id>,
          arguments: {
            command: <command>,
            arg1: 0
          }
        }

.. http:get:: /tool/ui/<tool_id>

    Serves the control or maintenance/cal UI for the tool_id specified

    **Example Request (jquery)**:

    ::

        $('#' + target_id).load("/tool/ui/<tool_id>", function(response, status, xhr) {
            if(status == "error"){$('#' + target_id).html("Unable to load");}});

    :query None: None
    :resheader Content-Type: content/json
    :statuscode 200: no error
    :statuscode 404: page not found
