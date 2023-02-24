# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
These are the valid non-percentile states that an `.Operation` can be in.
"""

from enum import IntEnum, unique


@unique
class OperationState(IntEnum):
    """
    :IDLE: has not been run yet, i.e. 0% completed
    :RUNNING: is now running, i.e. 1% done
    :COMPLETED: completed, i.e. 100%
    :WAITING_ON_TOOL: waiting to check out a busy tool
    :REQUEUE: data or tools are missing, requeue and re-run later
    :ERROR: exception/error, do not go on with dependent operations
    :RESULTFAILURE: result boundary failure
    :ABORTED: asked to shut down
    """

    IDLE = 0
    RUNNING = 1
    COMPLETED = 100
    WAITING_ON_TOOL = 105
    REQUEUE = 120
    ERROR = 130
    RESULTFAILURE = 140
    SKIPPED = 150
    ABORTED = 200
