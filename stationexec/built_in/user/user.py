# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
Tool for user session authentication and mode tracking
"""
import json
import bcrypt
import requests
import hashlib

import tornado.ioloop
import tornado.escape
from http import HTTPStatus

from stationexec.logger import log
from stationexec.toolbox.tool import Tool
from stationexec.toolbox.toolbox import get_tools
from stationexec.web.handlers import ExecutiveHandler
from stationexec.station.events import emit_event
from stationexec.station.events import InfoEvents
from stationexec.utilities.config import get_system_config

version = "1.0"
dependencies = []
default_configurations = {
    'mes_auth_endpoint': 'https://mfg-mes-srv01.mfg.apc2-sigma.com:8043/system/webdev/WS_ProductionTracking/validateUser'
}

VALID_ROLES = ['Engineer', 'Administrator', 'Technician']
ROLES_AND_FORBIDDEN_MODES = {
    'Technician': ('Engineering', 'Troubleshooting'),
    'Lead Technician': ('Engineering',)
    }
SSL_CERTIFICATE_PATH = get_system_config().get('ssl_certificate_path')

class User(Tool):
    """ Setup tool with configuration arguments """

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)

        mes_auth_endpoint = kwargs.get('mes_auth_endpoint')

        self.mes_auth_endpoint = mes_auth_endpoint if mes_auth_endpoint else default_configurations['mes_auth_endpoint']   
        self.mode = None
        self.role = None
        self.mes_roles = []

    def initialize(self):
        """ Prepare tool for operation """
        pass

    def verify_status(self):
        """ Check that tool is online; attempt to repair if not. Called every 5 seconds. """
        pass

    def shutdown(self):
        """ Cleanup tool for program shutdown """
        pass

    def on_ui_command(self, command, **kwargs):
        """ Command received from UI """
        pass

    def get_endpoints(self):
        """ Setup tool API """
        endpoints = [
            ("/tool/user/login", LoginHandler, {"user_tool": self}),
            ("/tool/user/logout", LogoutHandler, {"user_tool": self}),
            ("/tool/user/auth", AuthorizeHandler, {"user_tool": self}),
            ("/tool/user/create", CreateHandler, {"user_tool": self}),
        ]
        return endpoints

    @get_tools("mongo")
    def add_to_db(self, username, hashed_password, role, tools):
        tools.mongo.add_user(username, hashed_password, role)

    @get_tools("mongo")
    def get_user_info(self, username, tools):
        return tools.mongo.get_user(username)

    def handle_user_logout(self):
        self.mode = None
        self.role = None
        self.mes_roles = []

    def validate_credentials_mes(self, username:str, password:str):
        hashed_password = hashlib.sha512(password.encode()).hexdigest()

        payload = {
            'username': username,
            'password': hashed_password
        }

        verify = SSL_CERTIFICATE_PATH if SSL_CERTIFICATE_PATH else True
        
        try:
            response = requests.post(self.mes_auth_endpoint, json=payload, verify=verify)
        except Exception as ex:
            log.error(str(ex))
            return

        if not response.ok:
            log.error('Failed request to MES')
            return
        return response.json()

    def validate_user_mode(self, mode:str) -> bool:
        # MongoDB Roles (ex: 'Engineer')
        if self.role:
            forbidden_modes = ROLES_AND_FORBIDDEN_MODES.get(self.role)
            if forbidden_modes and mode in forbidden_modes:
                return False
        
        # MES Roles (ex: ['Engineer', 'Technician'])
        if self.mes_roles:
            # find role with lowest number of forbidden modes
            forbidden_modes = [] # ex: [('Engineering'), ('Engineering', 'Troubleshooting')]
            for role in self.mes_roles:
                modes = ROLES_AND_FORBIDDEN_MODES.get(role)
                if not modes:
                    # user has an unrestricted role
                    return True
                else:
                    forbidden_modes.append(modes)
            
            # check if provided mode is in shortest modes tuple
            shortest_forbidden_modes = min(forbidden_modes, key=len)
            if mode in shortest_forbidden_modes:
                return False

        return True

class BaseHandler(ExecutiveHandler):
    cookie_name = "user"

    def initialize(self, **kwargs):
        if "user_tool" in kwargs:
            self.user = kwargs["user_tool"]

    def get_current_user(self):
        return self.get_secure_cookie(self.cookie_name)

    async def hash_password(self, password, salt):
        """ Generate the hash for the provided password and salt """
        return await tornado.ioloop.IOLoop.current().run_in_executor(
            None,
            bcrypt.hashpw,
            tornado.escape.utf8(password),
            tornado.escape.utf8(salt),
        )


class CreateHandler(BaseHandler):
    async def post(self):
        try:
            body = tornado.escape.json_decode(self.request.body)
            username = body["username"]
            password = body["password"]
            role = body["role"]
        except (json.decoder.JSONDecodeError, KeyError):
            self.set_status(HTTPStatus.BAD_REQUEST)
            self.write({"reason": "invalid request body"})
            return

        user_info = self.user.get_user_info(username)
        if user_info:
            self.set_status(HTTPStatus.CONFLICT)
            self.write({"reason": "username already exists"})
            return

        if role not in VALID_ROLES:
            self.set_status(HTTPStatus.CONFLICT)
            self.write({"reason": f"Invalid role. Roles allowed are {VALID_ROLES}"})
            return

        # Generate the hash for the provided password
        hashed_password = await self.hash_password(password, bcrypt.gensalt())

        # Add user to database
        self.user.add_to_db(username, hashed_password, role)

        response = {
            "username": tornado.escape.xhtml_escape(username),
            "pwd_hash": tornado.escape.xhtml_escape(hashed_password),
            "role": tornado.escape.xhtml_escape(role),
        }
        self.set_status(HTTPStatus.OK)
        self.write(response)


class AuthorizeHandler(BaseHandler):
    async def get(self):
        # If not logged in
        if not self.current_user:
            log.warning("Failed to authorize user")
            self.set_status(HTTPStatus.UNAUTHORIZED)
            self.write({"status": "unauthorized"})
        else:
            if self.user.role:
                role = self.user.role
            elif self.user.mes_roles:
                role = ','.join(self.user.mes_roles)

            response = {
                "status": "authorized",
                "username": tornado.escape.xhtml_escape(self.current_user),
                "mode": tornado.escape.xhtml_escape(self.user.mode),
                "role": tornado.escape.xhtml_escape(role)
            }
            self.set_status(HTTPStatus.OK)
            self.write(response)


class LoginHandler(BaseHandler):
    async def validate_credentials_mongo(self, username, password, mode) -> bool:
        # Get user data from database
        user_info = self.user.get_user_info(username)
        if not user_info:
            self.set_status(HTTPStatus.UNAUTHORIZED)
            self.write({"reason": "username does not exist"})
            return False

        # Get password hash from user data
        # Ensure hash read from database is in UTF8 format
        password_hash = tornado.escape.utf8(user_info["password"])

        # Compute hashed password for provided plaintext password
        hashed_password = await self.hash_password(password, password_hash)

        # Validate password
        if hashed_password != password_hash:
            self.set_status(HTTPStatus.UNAUTHORIZED)
            self.write({"reason": "invalid password"})
            return False

        self.user.role = user_info["role"]

        return True

    def validate_credentials_mes(self, username:str, password:str, mode:str) -> bool:
        mes_response = self.user.validate_credentials_mes(username, password)

        if not mes_response:
            self.set_status(status_code=500)
            self.write({ 'reason': 'Failed request to MES' })
            return False
        if not mes_response.get('authenticated'):
            self.set_status(status_code=401)
            self.write({ 'reason': mes_response['errorMessage'] })
            return False

        # user credentials have been authenticated
        self.user.mes_roles = mes_response.get('roles')

        return True

    async def post(self):
        try:
            body = tornado.escape.json_decode(self.request.body)
            auth_method = body["authMethod"]
            username = body["username"]
            password = body["password"]
            mode = body["mode"]
            data_location = body.get('data_location')
        except (json.decoder.JSONDecodeError, KeyError):
            self.set_status(HTTPStatus.BAD_REQUEST)
            self.write({"reason": "invalid request body"})
            return

        if auth_method == 'mongo':
            valid_credentials = await self.validate_credentials_mongo(username, password, mode) 
        elif auth_method == 'mes':
            valid_credentials = self.validate_credentials_mes(username, password, mode)

        # validate user mode / role combination
        valid_mode = self.user.validate_user_mode(mode)
        if not valid_mode:
            self.set_status(status_code=401)
            self.write({"reason": f'User does not have access to {mode} mode'})
        
        if valid_credentials and valid_mode:
            # Store access token for user and record user's mode
            # Expires=None creates a session cookie (i.e. logs out when browser closed)
            self.set_secure_cookie(self.cookie_name, username, expires_days=None)
            self.user.mode = mode

            # Use event system to let other components know the user logged in
            event_data = {
                "username": username,
                "mode": mode,
                "role": self.user.role,
                "data_location": data_location
            }
            emit_event(InfoEvents.USER_LOGGED_IN, event_data)
            log.info(f'User: {username} Mode: {mode} Role: {self.user.role} logged in')


class LogoutHandler(BaseHandler):
    def post(self):
        user = self.get_current_user().decode("utf-8")
        log.info(f'User: {user} Mode: {self.user.mode} logged out')
        self.clear_cookie(self.cookie_name)
        self.user.handle_user_logout()

        # Use event system to let other components know the user logged out
        emit_event(InfoEvents.USER_LOGGED_OUT)
