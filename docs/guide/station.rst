Station Development
===================
A new station can be started by using the `se-gen` CLI tool. This will create a station folder filled with template
files for a station that the author can then edit to meet their needs (see the `CLI Utilities` section of this guide
for more details, usage instructions, and other helpful utilities).::

    # Create a 'special_delivery' station in the 'stations' folder of top-level 'stationexec' folder
    se-gen -t station -l stationexec/stations -n special_delivery

An individual station is made of three primary parts:

    1. Station Definition
    2. Sequence Operations
    3. Tool Manifest

Sequence Definition
-------------------
The sequence definition is made up of a JSON file (operations.json) and a Python file (operations.py).
These two files describe the connection and function of all operations and are used to define and
execute a sequence.

operations.json
^^^^^^^^^^^^^^^

Fields
""""""
id - Unique string ID that maps to the operation class name in the Python file
file - (optional)

operation_name - String display name of operation

description - String description of operation purpose

operation_results - List of objects defining the results that will be returned
from the operation. List can be empty, but the list must exist.

    result object fields:
    - name
    - description
    - type (see valid list below)
    - lower
    - upper

Current valid types:

.. hlist::
   :columns: 3

   * numeric
   * integer
   * float
   * text/plain
   * text/html
   * binary
   * image/jpeg
   * image/png
   * image/gif
   * image/bmp
   * audio/mpeg
   * audio/ogg
   * audio/*
   * audio/midi
   * audio/wav
   * video/mp4
   * video/ogg

dependency_list - List of "id" fields of other operations that must complete
before this operation is valid to run.

operation_data - Object containing parameters that the operation will need
for its functionality. These values may be constant, but may also refer to
the results from prior operations by prefixing the result name with 'result:',
e.g. if one operation produces a result names "index", a later operation
may use that result as data by specifying the value "result:index".

Example operation definition:

.. code-block:: javascript

    [
      {
        "id": "ExampleOperation01",
        "operation_name": "Example Operation",
        "description": "Creates a place for everything and puts everything in its place",
        "operation_results": [
          {
            "name": "thing01",
            "description": "first thing to be performed; should be greater than 12",
            "lower": 12
          },
          {
            "name": "thing02",
            "description": "second thing; should be in range 4459.2-4522.9",
            "lower": 4459.2,
            "upper": 4522.9
          }
        ],
        "dependency_list": [
        ],
        "operation_data": {
          "initial_value": 12.6,
          "offset_1": 2,
          "y-offset": 5
        }
      },
    ]

operations.py
^^^^^^^^^^^^^
prepare

operation_action

tool check-out/check-in

algorithm server

requeue

return states

- OperationState.COMPLETED, OperationState.ERROR, or OperationState.REQUEUE

overflow file

::

    from stationexec.logger import log
    from stationexec.sequencer.operation import Operation
    from stationexec.sequencer.operationstates import OperationState

    class ExampleOperation01(Operation):
        def prepare(self):
            # Optional preparation step; can use to determine if conditions are right
            if not <conditions required to run>:
                # Requeue this task if cannot run at this time
                log.info("Re-queuing")
                return OperationState.REQUEUE
            return OperationState.COMPLETED

        def operation_action(self, incoming_data, expected_results):
            log.info("I am class {0}".format(str(self.__class__)))

            # Check-out tool defined in manifest for operation
            self.checkout_tool('example_tool')

            # Get operational data from "operation_data" in JSON file
            start_value = incoming_data["initial_value"]

            # Store expected results (defined in "operation_results")
            self.save_result("thing01", 12.07)
            self.save_result("thing02", 4461.62)

            if <something is broken>:
                log.error("Cannot run - something is broken")
                return OperationState.ERROR
            time.sleep(1)

            return OperationState.COMPLETED

Station Definition
------------------

Station Tool Manifest
---------------------
::

    [
        {
            "tool_type": "example",
            "name": "Example",
            "tool_id": "example_tool",
            "configurations": {
                "port": 8001,
                "exposure": 3,
                "example_config": "value"
            }
        },
        {
            "tool_type": "example2",
            "name": "Example 2",
            "tool_id": "example2_tool",
            "configurations": {
                "amazing_thing1": 1,
                "amazing_thing2": 2,
                "amazing_thing3": "skymall"
            }
        },
    ]


Create a Station
----------------
Start by making a copy of the 'station_template' folder inside of 'stationexec/templates'
into the workspace of your choice inside a parent level station folder. The folder structure
should resemble the one below:

**Station Folder Structure**

- Parent Tool Folder
    - station_template - Folder
        - __init__.py - Required; empty
        - operations.json - Required
        - operations.py - Required
        - station.json - Required
        - station.py - Required
        - station_handler.py - Optional
        - tool_manifest.json - Required
        - ui
            - station_template_ui.html - Required
- __init__.py - Required; empty

This layout represents a tool of type 'station_template'. Change the names of things to
represent the tool that you are developing. For an example tool called Robot Station,
the names would be changed as follows:

* 'station_template' folder becomes 'robot_station'
* 'ui/station_template_ui.html' becomes 'ui/robot_station_ui.html'

'station_handler.py' is optional and does not have a controlled name so it
can be changed or removed as desired. If making edits to the file name, be
sure to adjust the import path at the top of the main station .py file to reflect
the change and new location. Also change the name of the html file rendered in the
handler to the new name of the file in the ui folder.
