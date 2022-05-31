# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1
import sys


def to_bytes(seq):
    """
    Convert a sequence to a bytes type

    Adapted from pyserial serialutil.py/to_bytes

    :param seq:
    :return:
    """
    major = sys.version_info[0]

    if isinstance(seq, bytes):
        return seq
    elif isinstance(seq, bytearray):
        return bytes(seq)
    elif isinstance(seq, memoryview):
        return seq.tobytes()
    elif isinstance(seq, str) and major == 3:
        # Python 3 Unicode string must have encoding - assume UTF-8
        return bytes(seq, 'UTF-8')

    # unicode is a valid keyword in Python2, but not Python3
    # @lint-ignore FLAKE8 F821 fb_flake8
    elif major == 2 and isinstance(seq, unicode):
        # Python 2 unicode explicit type
        try:
            return bytes(seq)
        except TypeError:
            # if using 'bytes' from built-ins, an encoding is required
            return bytes(seq, 'UTF-8')
    else:
        # handle list of integers and bytes (one or more items) for Python 2 and 3
        return bytes(bytearray(seq))
