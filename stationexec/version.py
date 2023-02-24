# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

version = "2.7"


change_log = {
    "2.7": "- Updated to use latest version of Arrow by removing deprecated datetime type."
           "- Added tools package folder to hello_prpl example station (as it is being searched for in latest version)"
           "- Updated station_storage to use latest version of sqlalchemy with deprecated Table[].exists ... using "
           "  inspect has_table to verify table exists"
           "- Modified DUT tool, default serial number to a text string.  If config does not exist, it throws an error"
           "- for some reason stationexec.__version__ doesn't exist.  added a call to read from this file to update."
           "- modified setup.py to remove python2 compat settings and to remove the version specification around arrow"
           "  and tornado."
           "- verified functionality in python 3.11"
}
