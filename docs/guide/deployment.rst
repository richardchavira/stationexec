Deployment
==========
On target machine:

    - Install stationexec library
    - Create project directory in user space (e.g. 'stationexec')
    - Create 'stations' and 'tools' folders in this directory
    - Populate the 'stations' and 'tools' folders with the stations and tools required for
      the deployment
    - Create the top level configuration .json file inside the top level folder (e.g. station_launch.json)
    - Launch the station::

        stationexec -f station_launch.json

