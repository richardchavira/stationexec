# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""This class defines ANSI color codes to change the cursor color

End with ENDC, which turns off all colors and modes.

Example:

.. code-block:: python

    import stationexec.colors
    print(Colors.WARNING + "Warning: something went wrong" + Colors.ENDC)

"""


class Colors(object):
    HEADER = '\033[95m'
    OKBLUE = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    INFO = '\033[45m'
    ENDC = '\033[0m'

    BLINK = '\033[5m'
    NOBLINK = '\033[25m'

    BOLD = '\033[1m'
    NOBOLD = '\033[22m'

    UNDERLINE = '\033[4m'
    NOUNDERLINE = '\033[24m'
