# User Tool

The User Tool is used for user session authentication and mode tracking

## Dependenices
#### StationExec tools required
- mongo

### StationExec
- verion 1.1.1.proto.dev0 or higher

#### Third party applications required
- None

## Usage
### Adding users
A valid user must be loaded into the database for login validation to function. A user can be added to the database by POST to the StationExec URL http://localhost:8888/tool/user/create with the following JSON body (an API tool such as Postman is useful for this). Valid roles are: Administrator, Engineer, Technician.
> Note: the password field in the JSON body is the plain text password.

~~~~~~~~~~~~~~~~~~~~~~~~~~
{
    "username":"string",
    "password":"string",
    "role":"string"
}
~~~~~~~~~~~~~~~~~~~~~~~~~~

#### Tool manifest definitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
{
    "tool_type": "user",
    "name": "User",
    "tool_id": "user",
    "configurations": {
        "mes_auth_endpoint": <<MES_user_authorization_endpoint>>
    }
}
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

## Release Notes
### 1.0
- SSL certificate path required for MES authentication