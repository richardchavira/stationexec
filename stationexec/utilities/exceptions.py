# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

from stationexec.utilities.error_codes import ErrorCode

class StationError(Exception):
    """ Custom exception to be thrown by Station """

    def __init__(self, module=None, code=None, message=None):
        """ make additional arguments optional so that class is pickleable """
        self.module = module
        self.code = code
        if not message:
            message = "Exception {0} in module {1}".format(code, module)
        super(StationError, self).__init__(message)


class InvalidAttribute(Exception):
    """Custom exception used when json files are missing required fields or have invalid values"""

    def __init__(self, message, field=None, filename=None):
        """ make additional arguments optional so that class is pickleable """
        self.field = field
        self.filename = filename
        super(InvalidAttribute, self).__init__(message)


class MissingResult(Exception):
    """Custom exception used when Operation is missing a result"""

    def __init__(self, message, field=None):
        """ make additional arguments optional so that class is pickleable """
        self.field = field
        super(self.__class__, self).__init__(message)


class ToolExistsException(Exception):
    """ Exception indicating an attempt to create a tool name that already exists. """

    def __init__(self, message):
        super(self.__class__, self).__init__(message)


class ToolNotExistsException(Exception):
    """ Exception indicating an attempt to check out a tool name that does not exist. """

    def __init__(self, message):
        super(self.__class__, self).__init__(message)


class ToolLockException(Exception):
    """ Exception indicating an attempt to lock or unlock a tool failed fatally. """

    def __init__(self, message):
        super(self.__class__, self).__init__(message)


class ToolUnavailableException(Exception):
    """ Exception indicating an tool offline and not available for use. """

    def __init__(self, message):
        super(self.__class__, self).__init__(message)


class ToolInUseException(Exception):
    """ Exception indicating a tool is in use by another process and not available. """

    def __init__(self, message):
        super(self.__class__, self).__init__(message)


class AbortException(Exception):
    """ Exception indicating that a Operation has detected a shutdown request. Has no message. """

    def __init__(self):
        super(self.__class__, self).__init__()


class ErrorCodeException(Exception):
    """ Exception to pass error codes up from tools and operations to database """

    def __init__(self, error_code: ErrorCode, debug_message=""):
        """ Send error code to operation 
            message is optional and may be included in the error_code object
        """
        self.error_code = error_code
        if debug_message != "":
            self.error_code.debug_message = debug_message
    
    def __str__(self):
        return self.error_code.__str__()

