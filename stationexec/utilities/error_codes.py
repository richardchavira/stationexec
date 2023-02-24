from enum import Enum, IntEnum, unique

from stationexec.utilities.uuidstr import get_uuid
from stationexec.utilities.time import format_datetime, get_local_time
from stationexec.utilities.config import get_system_config


class ErrorCode:

    def __init__(self, 
            error_code, 
            component_code=None, 
            debug_message="", 
            project_code=None, 
            operation=None
        ):
        self.operation = operation
        self.project_code = project_code
        self.component_code = component_code
        self.error_code = error_code
        self.debug_message = debug_message

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.error_code == other
        elif isinstance(other, ErrorCode):
            return self.error_code == other.error_code
    
    def __setattr__(self, key, value):
        self.__dict__[key] = value

        if key == 'error_code':
            self.refresh()
        if key == 'component_code':
            self.set_project_code()
        
    def refresh(self):
        self.timestamp = get_local_time()
        self.uuid = get_uuid()
        
    def get_dict(self) -> dict:
        return {
            "uuid": self.uuid,
            "operation": self.operation,
            "project_code": self.project_code,
            "component_code": self.component_code,
            "error_code": self.error_code,
            "debug_message": self.debug_message,
            "timestamp": format_datetime(self.timestamp)
        }

    def __str__(self) -> str:
        return "Project: {}, Component: {}, Error: {}, Message: {}".format(self.project_code, self.component_code, self.error_code, self.debug_message)

    def set_project_code(self):
        if self.component_code != None and self.project_code == None:
            self.project_code = get_system_config().get('project_code')
        if self.component_code == None:
            self.project_code = None            

@unique
class FailureCodes(IntEnum):
    @property
    def code(cls):
        return cls._value_

    NO_ERROR = 0
    UNDEFINED_ERROR = 1
    GENERAL_EXCEPTION = 2
    SKIPPED = 3
    ABORTED = 4
    FAILED_CONDITION = 5
    MISSING_RESULTS = 6

    NONE_RESPONSE = 10          # api call returned None, add api call to message
    FALSE_RESPONSE = 11         # api call returned False, add api call to message
    FW_STATUS_RESPONSE = 12     # api call returned status code, add response to debug_message
    WRONG_DATA_TYPE = 13        # response was not the expected data type
    WRONG_DATA = 14             # response was the right type, wrong data value
    NO_RESPONSE = 15            # Nothing returned, timeout


STATIONEXEC_PROJECT_CODE = 10
@unique
class ComponentCodes(IntEnum):
    @property
    def code(cls):
        return cls._value_

    STATION_EXEC = 100
    OPERATION = 101
    TOOL = 102


def output_codes(code_enum: Enum, output_func=print):
    for member in code_enum:
        output_func("{0}, {1}".format(member.code, member.name))

if __name__ == "__main__":
    print("************** Error/Failure Codes **************")
    output_codes(FailureCodes)

    print("\n************** StationExec Component Codes **************")    
    output_codes(ComponentCodes)

    print("\n************** Project Codes **************")    
    print("{0}, StationExec project".format(STATIONEXEC_PROJECT_CODE))





