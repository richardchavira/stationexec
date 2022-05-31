Station Executive
=================
Station Executive is a light-weight, flexible software framework for sequencing tasks and interacting with external
data sources - including physical hardware - in a networked context.

Each `Station` is comprised of a series of `operations` and a set of `Tools`. The `operations` are intelligently
executed based upon data-flow dependencies and in parallel (as OS and hardware support allows). A `tool` is any
source or sink of data that can be used to accomplish the tasks (anything from a robot to a database).


Quick Start
-----------
**Run in command line (after installation):**::

    se-hello 8888

Open your browser and navigate to 'http://localhost:8888' to view the main UI.


Installation Options
--------------------
**From distributed package**::

    # Windows
    pip install stationexec-<version>-py2.py3-none-any.whl

    # Linux as User
    pip install --user stationexec-<version>-py2.py3-none-any.whl

    # Linux as Root
    sudo pip install stationexec-<version>-py2.py3-none-any.whl

**Running From Repository Clone**::

    # Editable installation
    pip install -e .
    se-hello 8888

**Python Virtualenv**::

    # Fedora (change 2 to 3 for Python 3) - Run in project folder
    sudo yum install python2-virtualenv
    virtualenv-2 env2
    source env2/bin/activate
    pip install stationexec-<version>-py2.py3-none-any.whl

Platform Support
----------------

+------------+------------+------------+--------------------+------------------------------------+
| **OS**     | **32bit**  | **64bit**  |**Python Version**  | **Tested**                         |
+------------+------------+------------+--------------------+------------------------------------+
| Windows    |  Untested  |   Yes      | 2.7.9+, 3.6        | Windows 10                         |
+------------+------------+------------+--------------------+------------------------------------+
| Linux      |  Untested  |   Yes      | 2.7.9+, 3.6        | Fedora 28/29, Centos 7, Ubuntu 16+ |
+------------+------------+------------+--------------------+------------------------------------+
| ARM        |  Yes       |   Yes      | 2.7.9+, 3.6        | Debian                             |
+------------+------------+------------+--------------------+------------------------------------+
| Mac        |  Untested  |   Yes      | 2.7.9+             | OSX 10.10+                         |
+------------+------------+------------+--------------------+------------------------------------+
