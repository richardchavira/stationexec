# Copyright 2004-present Facebook. All Rights Reserved.

import base64
import uuid
from typing import Optional


def get_uuid():
    return uuid2str(uuid.uuid1())


def get_uuid_base64():
    return base64.b64encode(uuid.uuid1().bytes)


def uuid2str(auuid):
    # type: (uuid) -> Optional[str]
    """
    Return a representation of a UUID for storage into a database

    :param UUID auuid: a `.UUID` object
    :return: a string with the dashes removed, or None if the argument was None
    """
    if auuid is None:
        return None
    return str(auuid).replace('-', '')


def str2uuid(astr):
    # type: (str) -> Optional[uuid]
    """
    Convert a string representation of a UUID from a database into a Python UUID object.

    :param str astr: a UUID string from a database
    :return: a UUID object, or None if the argument was None
    """
    if astr is None:
        return None
    return uuid.UUID(astr)
