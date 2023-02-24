# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
Tool for storing data into a MongoDB

Note: See station_storage module for details on the available built-in
data storage.
"""

from typing import List
import requests
import json
from stationexec.built_in.dut.dut import DEFAULT_SERIAL_NUMBER

from stationexec.toolbox.tool import Tool
from stationexec.station.events import InfoEvents, RetrievalEvents, StorageEvents, emit_event
from stationexec.web.handlers import ExecutiveHandler
from stationexec.utilities import config
from stationexec.utilities.time import TIMESTAMP_FORMAT, get_utc_now, format_datetime
from stationexec.logger import log
from stationexec.toolbox.toolbox import get_tools

version = "2.0"
dependencies = []
default_configurations = {}


SSL_CERTIFICATE_PATH = config.get_system_config().get('ssl_certificate_path')
SSL_VERIFICATION = SSL_CERTIFICATE_PATH if SSL_CERTIFICATE_PATH else True

def check_save_data(func):
    """Decorator to decide whether to save data to mongodb

    Args:
        func (function): function to be decorated
    """

    def wrapper_fuction(mongo_instance, *args, **kwargs):
        data_location = mongo_instance.data_location
        if data_location is None or mongo_instance.db_endpoints.get(data_location):
            # save data if data_location not set or data_location has associated endpoint 
            return func(mongo_instance, *args, **kwargs)
        else:
            # allow only users to be created if save_data is false
            # TODO: once data storage is consolidated, this won't be needed
            if 'password' in args[1]:
                return func(mongo_instance, *args, **kwargs)

    return wrapper_fuction


class Mongo(Tool):

    """ Setup tool with configuration arguments """

    def __init__(self, **kwargs):
        super(Mongo, self).__init__(**kwargs)

        self.db_name = 'protoline_se'
        self.data_location = None
        self._hostname = kwargs.get('hostname')
        
        db_endpoints = config.get_system_config().get('db_endpoints') 
        self.db_endpoints = db_endpoints if db_endpoints else {}

        # later initialized with data from user tool
        self.username = None
        self.user_mode = None
        self.user_role = None
        self.tools = {}

        # later initialized with data from dut tool
        self.dut_serial_number = None

        self.dut_data = {}
        self.routing_data = {}

        # Register for events that require data to be captured
        self.listen_for_event(StorageEvents.ON_SEQUENCE_START, self.on_sequence_start)
        self.listen_for_event(StorageEvents.ON_SEQUENCE_END, self.on_sequence_end)
        self.listen_for_event(InfoEvents.SEQUENCE_FINISHED, self.clear_sequence_tag_data)
        self.listen_for_event(StorageEvents.ON_OPERATION_START, self.on_operation_start)
        self.listen_for_event(StorageEvents.ON_OPERATION_END, self.on_operation_end)
        self.listen_for_event(StorageEvents.ON_ERROR_CODE, self.on_error_code)
        self.listen_for_event(StorageEvents.ON_RESULT_STORE, self.on_result_store)
        self.listen_for_event(StorageEvents.ON_DATA_STORE, self.on_data_store)
        self.listen_for_event(InfoEvents.USER_LOGGED_IN, self.on_login)
        self.listen_for_event(InfoEvents.USER_LOGGED_OUT, self.on_logout)
        self.listen_for_event(StorageEvents.ON_ADD_DUT, self.add_dut)
        self.listen_for_event(RetrievalEvents.GET_DUT_DATA, self.get_dut)
        self.listen_for_event(InfoEvents.DUT_SERIAL_NUMBER_UPDATE, self.on_dut_serial_number_update)
        self.listen_for_event(InfoEvents.TOOLS_LOADED, self.on_tools_loaded)
        self.listen_for_event(StorageEvents.ON_UPDATE_STATION, self.on_update_station)
        self.listen_for_event(RetrievalEvents.GET_STATION_DATA, self.get_station_data)
        self.listen_for_event(StorageEvents.ON_REGISTER_STATION, self.on_register_station)
        self.listen_for_event(InfoEvents.ROUTING_DATA_UPDATE, self.on_routing_data_update)

        self.connected = True

        self.sequence_tag_data = self.initialize_sequence_tags()
        self.station_tag_data = self.load_station_tag_data()

    @property
    def hostname(self):
        alternate_hostname = self.db_endpoints.get(self.data_location)
        return alternate_hostname if alternate_hostname else self._hostname

    def initialize(self):
        """ Prepare tool for operation """
        pass

    def verify_status(self):
        """" Check that tool is online; attempt to repair if not. Called every 5 seconds. """
        return self.update()

    def update(self):
        """Test Connection to REST API"""

        response = requests.get(self.hostname, verify=SSL_VERIFICATION)
        if response.ok:
            self.connected = True
        else:
            self.connected = False

        status = "Connected" if self.connected else "Not Connected"

        self.value_to_ui(f"{self.tool_id}_db_status", status)
        self.value_to_ui(f"{self.tool_id}_db_hostname", self.hostname)
        self.value_to_ui(f"{self.tool_id}_db_name", self.db_name)

        return self.connected

    def shutdown(self):
        """ Cleanup tool for program shutdown """
        pass

    def on_ui_command(self, command, **kwargs):
        """ Command received from UI """
        pass

    def get_endpoints(self):
        """ Setup tool API """
        endpoints = [
            ('/tool/mongo/update', UpdateHandler, {"tool": self}),
            ('/tool/mongo/uidata', UIDataHandler, {"tool": self})
        ]
        return endpoints

    def initialize_sequence_tags(self):
        station_config_path = config.get_all_paths().get('station_config')
        if station_config_path:
            station_config_data = config.load_config(station_config_path)
            sequence_tags = station_config_data.get('sequence_tags')
            return {tag: '' for tag in sequence_tags} if sequence_tags else None
        return None

    def set_sequence_tag_data(self, data):
        if data:
            for tag, value in data.items():
                 self.sequence_tag_data[tag] = value

    def clear_sequence_tag_data(self, **kwargs):
        if self.sequence_tag_data:
            for key in self.sequence_tag_data:
                self.sequence_tag_data[key] = ''

    def load_station_tag_data(self):
        station_config_path = config.get_all_paths().get('station_config')
        if station_config_path:
            station_config_data = config.load_config(station_config_path)
            station_tags = station_config_data.get('station_tags')
            return station_tags if station_tags else None
        return None

    @check_save_data
    def insert_one(self, collection, data, **kwargs):
        """Handles data inserts depending on self.data_location

        Args:
            collection (string): name of collection to save data
            data (dict): dictionary of data valid for pymongo API
        """

        
        response = requests.post(f'{self.hostname}/{collection}', json=data, verify=SSL_VERIFICATION)

        uuid = data.get('uuid', 'None')
        operation_uuid = data.get('operation', 'None')
        if collection in ['results', 'data', 'error_codes']:    
            log.info(f"table={collection}, uuid={uuid}, operation_uuid={operation_uuid}, response_code={response.status_code}")
        else:
            log.info(f"table={collection}, uuid={uuid}, response_code={response.status_code}")

        if not response.ok:
            log.error(
                f"Remote Database error: HTTP code {response.status_code}, "
                + f'{response.reason}'
            )
            log.error(
                f'Failed to add the following record on table {collection} with uuid {uuid}:'
            )
            log.error(json.dumps(data))
            self.ui_log(
                f'Failed to add record to remote database on table {collection} with uuid {uuid}'
            )

    @check_save_data
    def find_one_and_update(self, collection, collection_filter, update, **kwargs):
        """Handles the 'find_one_and_update' method for pymongo

        Args:
            collection (string): name of collection to update
            collection_filter (string): filter in the following format: {{"key": "value"}}
            update (dict): dictionary with key(s)/value(s) to be updated in mongodb
        """

        with requests.Session() as session:
            url = f'{self.hostname}/{collection}'
            response = session.get(url + '?where=' + collection_filter, verify=SSL_VERIFICATION)

            if response.ok:
                json_response = response.json()

                # check if it returns at least one document from collection
                if json_response.get('_items'):
                    _id = json_response.get('_items')[0].get('_id')
                else:
                    log.info(
                        f'could not find document in {collection} with criteria'
                        + f'{collection_filter}'
                    )
                    return None

                # update document if one is found
                url2 = url + '/' + _id
                response2 = session.patch(url2, json=update)

                if response2.ok:
                    response3 = session.get(url2)
                    final_json_response = response3.json()
                    log.info(f'the document {collection + "/" + _id} has been updated')
                    return final_json_response
                else:
                    log.error(f'error updating document in {collection} collection')
                    return None
            else:
                log.error(
                    f'error finding document with following criteria {collection_filter}'
                )
                return None

    def on_dut_serial_number_update(self, **kwargs):
        self.dut_serial_number = kwargs.get('serial_number')

    def get_dut(self, serial_number, **kwargs):
        # Find the document for this serial number
        # Returns None if serial number does not exist in the database
        endpoint = f'{self.hostname}/duts?where={{"serial_number":"{serial_number}"}}'
        response = requests.get(endpoint, verify=SSL_VERIFICATION)

        if response.ok:
            json_response = response.json()
            dut = json_response.get('_items')
            if not dut:  # check if empty array
                return None
            else:
                dut_data = dut[0]
                serial_number = dut_data.get('serial_number')
                test_count = self.get_dut_test_count(serial_number)
                
                return {
                    'serial_number': serial_number,
                    'test_count': test_count
                }
        else:
            return None

    def add_dut(self, data, **kwargs):
        for dut_data in data:    
            dut = {"serial_number": dut_data.get('serial_number')}
            self.insert_one('duts', dut)

    def get_dut_sequence_uuids(self, serial_number: str) -> List:
        # Find the sequence start uuids for this serial number

        endpoint = f'{self.hostname}/sequence_starts?where={{"serial_number":"{serial_number}"}}'
        response = requests.get(endpoint, verify=SSL_VERIFICATION)

        if response.ok:
            json_response = response.json()
            sequence_starts = json_response.get('_items')

            sequence_start_uuids = [sequence['uuid'] for sequence in sequence_starts if sequence.get('uuid')]
            return sequence_start_uuids
        else:
            return []

    def get_dut_sequence_ends(self, uuids):
        # Find the cooresponding sequence ends for uuids

        # uuids may be None
        if uuids:
            endpoint = f'{self.hostname}/sequence_ends'
            response = requests.get(endpoint, verify=SSL_VERIFICATION)

            if response.ok:
                json_response = response.json()
                sequence_ends = json_response.get('_items')
                
                dut_sequence_ends = []
                for sequence in sequence_ends:
                    uuid = sequence.get('uuid') 
                    if uuid:
                        if uuid in uuids and sequence['pass']:
                            dut_sequence_ends.append(sequence)
                return dut_sequence_ends
            else:
                return []
        else:
            return []

    def get_dut_test_count(self, serial_number: str) -> int:
        sequence_uuids = self.get_dut_sequence_uuids(serial_number)
        sequence_ends = self.get_dut_sequence_ends(sequence_uuids)
        return len(sequence_ends)

    def on_tools_loaded(self, **data):
        self.update_attribute_with_event_data('tools', data)

    def on_login(self, **kwargs):
        # Capture username and mode for recording with sequence data
        self.username = kwargs["username"]
        self.user_mode = kwargs["mode"]
        self.user_role = kwargs["role"]
        self.data_location = kwargs.get('data_location')

    def on_logout(self, **kwargs):
        self.username = None
        self.user_mode = None
        self.user_role = None
        self.data_location = None
    

    def on_routing_data_update(self, **data):
        self.update_attribute_with_event_data('routing_data', data)

    def update_attribute_with_event_data(self, attribute, data):
        data.pop('_event', None)
        setattr(self, attribute, data)

    def on_register_station(self, data, evt=None):
        """
        Register a new station in the stations collection

        Method gets called by executive
        """

        # valid only if this tool registered to event
        if data[0].get('_source') != 'tool.mongo':
            return
        log.debug(3, "registering station in mongo")

        for station in data:
            station = {
                "uuid": station.get("uuid"),
                "variant": station.get("variant"),
                "instance": station.get("instance"),
                "macaddress": station.get("macaddress"),
                "hostname": station.get("hostname"),
                "location": station.get("location"),
                "lineid": station.get("lineid"),
                "info": station.get("info"),
                "preferences": station.get("preferences"),
                "created": station.get("created").strftime(TIMESTAMP_FORMAT)[:-3],
                "updated": station.get("created").strftime(TIMESTAMP_FORMAT)[:-3],
            }
            self.insert_one('stations', station)

    def on_update_station(self, data, evt=None):
        """

        :param list data: stations to update
        :param str evt: event the data came from
        :return: None
        """

        for new_station_info in data:
            instance = new_station_info.get("instance")
            variant = new_station_info.get("variant")
            filter = f'{{"variant": "{variant}", "instance": "{instance}"}}'

            update = {
                "hostname": new_station_info.get("hostname"),
                "macaddress": new_station_info.get("macaddress"),
                "location": new_station_info.get("location"),
                "lineid": new_station_info.get("lineid"),
                "preferences": new_station_info.get("preferences"),
                "info": new_station_info.get("info"),
                "updated": get_utc_now().strftime(TIMESTAMP_FORMAT)[:-3],
            }
            self.find_one_and_update('stations', filter, update)

    def on_sequence_start(self, data, evt=None):
        """
        Setup a sequence document from the start event.
        """
        
        dut_serial_number = self.dut_serial_number if self.dut_serial_number else DEFAULT_SERIAL_NUMBER

        for seq_start in data:
            seq_start["library_versions"].update(self.tools)
            # Add the data for the start event and put placeholders
            # for the data collected when the sequence ends
            start_data = {
                "uuid": seq_start.get("uuid"),
                "username": self.username,
                "mode": self.user_mode,
                "role": self.user_role,
                "serial_number": dut_serial_number,
                "station_uuid": seq_start.get("station"),
                "station_version": seq_start.get("version"),
                "tool_versions": seq_start.get("library_versions"),
                "start": seq_start.get("created").strftime(TIMESTAMP_FORMAT)[:-3],
                "sequence_tags": self.sequence_tag_data,
                "route_qualifier_name": self.routing_data.get('route_qualifier_name'),
                "route_qualifier_value": self.routing_data.get('route_qualifier_value')
            }
            if self.station_tag_data:
                start_data["station_tags"] = self.station_tag_data

            self.insert_one('sequence_starts', start_data)

    def on_sequence_end(self, data, evt=None):
        """
        Update the sequence document created in the sequence start event
        """
        for seq_end in data:
            # Update document with matching sequence UUID
            end_data = {
                # Note: these keys must match those created
                # in the sequence start event handler
                "uuid": seq_end.get("uuid"),
                "end": seq_end.get("created").strftime(TIMESTAMP_FORMAT)[:-3],
                "pass": seq_end.get("passing"),
                "info": seq_end.get("info"),
                "duration_ms": seq_end.get("duration_ms"),
            }
            self.insert_one('sequence_ends', end_data)

    def on_operation_start(self, data, evt=None):
        """
        Add an operation to the sequence's operations array
        """
        for op_start in data:
            # Add the data for the start event and put placeholders
            # for the data collected when the operation ends
            operation = {
                "uuid": op_start.get("uuid"),
                "sequence": op_start.get("sequence"),
                "name": op_start.get("name"),
                "description": op_start.get("description"),
                "priority": op_start.get("priority"),
                "info": op_start.get("info"),
                "start": op_start.get("created").strftime(TIMESTAMP_FORMAT)[:-3],
            }
            self.insert_one('operation_starts', operation)

    def on_operation_end(self, data, evt=None):
        """
        Update the operations array index created in the operation start event
        """
        for op_end in data:
            # Update sequence operation with matching operation UUID
            op_data = {
                # Note: these keys must match those created
                # in the operation start event handler
                "uuid": op_end.get("uuid"),
                "end": op_end.get("created").strftime(TIMESTAMP_FORMAT)[:-3],
                "duration_ms": op_end.get("duration_ms"),
                "exitcode": op_end.get("exitcode"),
                "pass": op_end.get("passing"),
                "info": op_end.get("info"),
                "waittime": op_end.get("waittime_ms")
            }
            self.insert_one('operation_ends', op_data)
    
    def on_error_code(self, data, evt=None):
        """
        Save error code entry to table
        'created' is usually added by the caller
        """
        for err_code in data:
            err_code_data = {
                "uuid": err_code.get("uuid"),
                "operation": err_code.get("operation"),
                "project_code": err_code.get("project_code"),
                "component_code": err_code.get("component_code"),
                "error_code": err_code.get("error_code"),
                "debug_message": err_code.get("debug_message"),
                "timestamp": err_code.get("timestamp"),
                "created": format_datetime(err_code.get("created"))
            }
            self.insert_one('error_codes', err_code_data)

    def on_result_store(self, data, evt=None):
        """
        Add a saved result to the operation's results array
        """
        for result in data:
            result_data = {
                # The value itself is considered Operand 1; result < operand2 or
                # result inrange(op2, op3)
                "uuid": result.get("uuid"),
                "operation": result.get("operation"),
                "name": result.get("name"),
                "description": result.get("description"),
                "value": result.get("value"),
                "pass": result.get("passing"),
                "operator": result.get("operator"),
                "operand2": result.get("operand2"),
                "operand3": result.get("operand3"),
                "created": result.get("created").strftime(TIMESTAMP_FORMAT)[:-3],
            }
            self.insert_one('results', result_data)

    def on_data_store(self, data, evt=None):
        """
        Add a saved data point to the operation's data array
        """
        for data_object in data:
            data_store = {
                "uuid": data_object.get("uuid"),
                "operation": data_object.get("operation"),
                "name": data_object.get("name"),
                "identifier": data_object.get("identifier"),
                "description": data_object.get("description"),
                "value": data_object.get("value"),
                "mimetype": data_object.get("mimetype"),
                "size": data_object.get("size"),
                "info": data_object.get("info"),
                "created": data_object.get("created").strftime(TIMESTAMP_FORMAT)[:-3],
            }
            self.insert_one('data', data_store)

    def add_user(self, username, hashed_password, role):
        self.insert_one(
            'users', {'username': username, 'password': hashed_password, 'role': role}
        )

    def get_user(self, username):

        endpoint = f'{self.hostname}/users?where={{"username": "{username}"}}'
        response = requests.get(endpoint, verify=SSL_VERIFICATION)

        if response.ok:
            json_response = response.json()
            return json_response.get('_items')[0]
        else:
            return None

    def get_station_data(self, instance, hostname, mac_address, **kwargs):
        """

        :param str variant: type or class of station
        :param str instance: specific instance of station
        :param kwargs:

        method gets called by executive
        """
        endpoint = f'{self.hostname}/stations?where={{"instance": "{instance}", "hostname": "{hostname}", "macaddress": "{mac_address}"}}'

        # valid only if this tool registered to event
        if kwargs.get('source') != 'tool.mongo':
            return
        response = requests.get(endpoint, verify=SSL_VERIFICATION)
        log.debug(3, "getting station data from mongo")
        if response.ok:
            json_response = response.json()
            if json_response.get('_items'):
                return json_response.get('_items')[0]
            else:
                return None
        else:
            return None

class UpdateHandler(ExecutiveHandler):
    def initialize(self, **kwargs):
        self.tool = kwargs["tool"]

    def get(self):
        connected = self.tool.update()
        self.write({ connected: connected })

class UIDataHandler(ExecutiveHandler):
    """
    This endpoint recieves data from UI inputs
    """

    def initialize(self, **kwargs):
        self.tool = kwargs["tool"]

    def get(self):
        self.write(
            {
                "sequence_tag_data": self.tool.sequence_tag_data,
                "station_tag_data": self.tool.station_tag_data,
                "data_locations": list(self.tool.db_endpoints.keys()),
                "data_location": self.tool.data_location
            }
        )

    def post(self):
        data = self.json_args
        if data:
            self.tool.set_sequence_tag_data(data)
            self.write(data)
