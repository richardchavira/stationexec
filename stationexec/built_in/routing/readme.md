# Routing Tool
The Routing tool is used to communicate DUT information to the MES system.

## Dependenices
#### StationExec tools required
- user
- dut

## Usage
Routing is enforced only in the "Production" user mode.

### Configuration
Add the following to your tool_manifest":
~~~~~~~~~~~~~~~~~~~~~~
    {
        "tool_type": "routing",
        "name": "Routing",
        "tool_id": "routing",
        "configurations":{
            "mes_endpoint": <<mes_rest_api_url>>,
            "route_qualifier_name": <<route_qualifier_name>>,
            "route_qualifier_values": <<route_qualifier_values>>
        }
    }
~~~~~~~~~~~~~~~~~~~~~~

## Release Notes
### 2.0
- SSL certificate path required for MES routing 
