# Mongo Tool
The Mongo tool is used to connect to and communicate with a mongo database.
Communication to database is through a REST API and not directly with pymongo driver

## Usage
#### Mongo Database
A mongo database must be accessible (for read and write) from the tool.

### Configuration
Add the following to your tool_manifest":
~~~~~~~~~~~~~~~~~~~~~~
    {
        "tool_type": "mongo",
        "name": "Mongo",
        "tool_id": "mongo",
        "configurations":{
            "hostname": <<host_name_rest_api>>
        }
    }
~~~~~~~~~~~~~~~~~~~~~~

## Release Notes
### 2.0
- Communicate with DUT tool via events only
### 1.4
- Use SSL certificate for requests if specified at station
### 1.3
- Use DUT default serial number if no serial number input by user