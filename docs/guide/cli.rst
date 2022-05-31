CLI Utilities
=============

Stationexec provides several command line utilities to assist the author, developer, and user
in all of their tasks. These entry-points are installed when the stationexec library is installed
on the machine and can be executed directly by name in a command line on any operating system.

se-hello
--------
The example 'hello-world' style program for stationexec. Run this to experience an example run of
stationexec and see a station and tools in action. ::

    se-hello 8888

Navigate to http://localhost:8888 in a browser to interact with the example

se-setup
--------
Setup folder structure of stationexec

se-start
--------
The stationexec launcher creates a running instance of a station. The run command pairs with the
system configuration file that can add to or override station-level configuration options for
this run.

e.g. Launch the station 'robot_manager' viewable at port 8448 at debug level 2. ::

    se-start robot_manager --port 8448 --debug 2

Options
'''''''
+---------------------+-----------+--------------------------------------------------+-------------+
| **Command**         | **Short** | **Help**                                         | **Type**    |
+---------------------+-----------+--------------------------------------------------+-------------+
| --debug             | -d        | verbosity level for logging (default 0)          | numeric     |
+---------------------+-----------+--------------------------------------------------+-------------+
| --instance          | -l        | unique name for running station instance         | string      |
+---------------------+-----------+--------------------------------------------------+-------------+
| --name              | -n        | proper name for running station instance         | string      |
+---------------------+-----------+--------------------------------------------------+-------------+
| --port              | -p        | server port number (default 8888)                | numeric     |
+---------------------+-----------+--------------------------------------------------+-------------+
| --threads           | -t        | max parallel operation threads (default 10)      | numeric     |
+---------------------+-----------+--------------------------------------------------+-------------+
| --dev               |           | development mode flag                            |             |
+---------------------+-----------+--------------------------------------------------+-------------+
| --file              | -f        | file that contains any configurations            | string path |
+---------------------+-----------+--------------------------------------------------+-------------+

se-tool
-------
Options:
gen - generate a new tool
launch - launch a named tool for testing and debugging
list - show all tools found in the system ::

    se-tool launch exampletool

se-which
--------
Show the install location of stationexec
