# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import arrow
from arrow.arrow import datetime


def utc_to_local(dt):
    dt = arrow.get(dt)
    return dt.to("local").datetime


def local_to_utc(dt):
    dt = arrow.get(dt)
    dt = dt.replace(tzinfo="local")
    return dt.to("UTC").datetime


def get_local_time():
    return arrow.now().datetime


def get_utc_now():
    return arrow.utcnow().datetime


def to_timestamp(dt, is_local_time=False):
    if isinstance(dt, datetime):
        return dt.timestamp()
    else:
        dt = arrow.get(dt)
        if is_local_time:
            # Assume time given in local time - assign local timezone info
            dt = local_to_utc(dt)
        return dt.timestamp()


def to_datetime(ts, local=False):
    if local:
        return utc_to_local(ts).datetime
    else:
        return arrow.get(ts).datetime


if __name__ == "__main__":
    """
    from datetime import datetime

    cardinal_utc_time = arrow.get(datetime(2000, 1, 1, 1, 1, 1))
    utc_timestamp = cardinal_utc_time.timestamp()
    primary_datetime = datetime(2000, 1, 1, 1, 1, 1)
    
    assert(to_timestamp(cardinal_utc_time) == utc_timestamp)
    assert(to_timestamp(primary_datetime) == utc_timestamp)
    assert(to_timestamp(primary_datetime, is_local_time=False) == utc_timestamp)

    assert(to_datetime(utc_timestamp))
    """
