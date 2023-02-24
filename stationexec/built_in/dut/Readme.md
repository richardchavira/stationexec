# DUT Tool

The DUT Tool is used for interfacing with the DUT and tracking DUT status

## Dependenices
#### StationExec tools required
- mongo

## Usage
#### DUT Routing
DUT Routing is a feature to track the DUT status/station and displays the expected station.
A DUT route must be present in the MongoDB used by the mongo tool, refer to the mongo tool manifest to determine the database location. The collection name must be dut_route. An example DUT route route document:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
{
    "stations": ["hello_prpl", "hello_prpl2"]
}
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#### Tool manifest definitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
{
    "tool_type": "dut",
    "name": "DUT",
    "tool_id": "dut",
    "configurations": {
	"id_patterns": ["\\w{5}", "\\w{6}"]
  }
}
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

## Release Notes

### 2.1
- Added serial_number getter

### 2.0
- Remove routing methods
- Refactor mechanisms to get and add DUTs to use events rather than direct calls to mongo tool methods
- Refactor set_serial_number logic
### 1.1
- Use default serial number if dev == true

