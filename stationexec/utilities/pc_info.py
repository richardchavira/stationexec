import re
import uuid
import platform


def get_mac_address():
    """Gets the PC's mac address

    Returns:
        str: mac address formatted as xx:xx:xx:xx:xx:xx
    """

    # source: https://www.geeksforgeeks.org/extracting-mac-address-using-python/
    return (':'.join(re.findall('../..', '%012x' % uuid.getnode())))


def get_hostname():
    """Gets the PC's hostname

    Returns:
        str: host name of PC
    """
    return platform.node()
