# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1


"""
Routing Tool
"""
import requests

from stationexec.logger import log
from stationexec.toolbox.tool import Tool
from stationexec.web.handlers import ExecutiveHandler
from stationexec.station.events import InfoEvents, emit_event
from stationexec.utilities.config import get_system_config

version = "2.0"
dependencies = []
default_configurations = {
    'mes_endpoint': 'https://mfg-mes-srv01.mfg.apc2-sigma.com:8043/system/webdev/WS_ProductionTracking/getStationExecutable'
}

SSL_CERTIFICATE_PATH = get_system_config().get('ssl_certificate_path')

class Routing(Tool):

    def __init__(self, **kwargs):
        """ Setup tool with configuration arguments """

        super(Routing, self).__init__(**kwargs)

        mes_endpoint = kwargs.get('mes_endpoint')

        self.mes_endpoint = mes_endpoint if mes_endpoint else default_configurations['mes_endpoint']        
        self.work_order_number = None
        self.route_qualifier_name = kwargs.get('route_qualifier_name')
        self.route_qualifier_value_options = kwargs.get('route_qualifier_values')
        self.route_qualifier_value = None
        self.mes_response_message = None
        self.dut_serial_number = None
        self.user_mode = None
        self.station_variant = None

        self.listen_for_event(InfoEvents.DUT_SERIAL_NUMBER_UPDATE, self.on_dut_serial_number_update)
        self.listen_for_event(InfoEvents.USER_LOGGED_IN, self.on_user_login)
        self.listen_for_event(InfoEvents.STATION_LOADED, self.on_station_load)
        self.listen_for_event(InfoEvents.SEQUENCE_FINISHED, self.on_sequence_finish)

    def initialize(self):
        """ Prepare tool for operation """
        pass

    def verify_status(self):
        """ Check that tool is online; attempt to repair if not. Called every 5 seconds. """
        self.update_ui()  
        
        # Only enforce routing in Production mode
        if self.user_mode != 'Production':
            return True
        
        if self.work_order_number:
            return True
        return False

    def shutdown(self):
        """ Cleanup tool for program shutdown """
        pass

    def on_ui_command(self, command, **kwargs):
        """ Command received from UI """
        pass

    def on_dut_serial_number_update(self, **kwargs):
        self.dut_serial_number = kwargs.get('serial_number')

    def on_user_login(self, **kwargs):
        self.user_mode = kwargs.get('mode')

    def on_station_load(self, **kwargs):
        self.station_variant = kwargs.get('variant')

    def on_sequence_finish(self, **kwargs):
        self.work_order_number = None
        self.route_qualifier_value = None
        self.mes_response_message = None
        self.dut_serial_number = None

    def get_endpoints(self):
        """ Setup tool API """
        endpoints = [
            (f"/tool/{self.tool_id}/work-order-data", WorkOderDataHandler, {"tool": self})
        ]
        return endpoints

    def update_ui(self):
        self.value_to_ui(f"{self.tool_id}_mes_message", str(self.mes_response_message))
        self.value_to_ui(f"{self.tool_id}_work_order_number", str(self.work_order_number))
        self.value_to_ui(f"{self.tool_id}_route_qualifier_name", str(self.route_qualifier_name))
        self.value_to_ui(f"{self.tool_id}_route_qualifier_value", str(self.route_qualifier_value))

    def send_work_order_payload_to_mes(self, work_order_number, route_qualifier_value):
        payload = {
            'WorkOrderNumber': work_order_number,
            'SerialNumber': self.dut_serial_number,
            'Variant': self.station_variant,
            'RouteQualifierName': self.route_qualifier_name,
            'RouteQualifierValue': route_qualifier_value
        }

        verify = SSL_CERTIFICATE_PATH if SSL_CERTIFICATE_PATH else True
        
        try:
            response = requests.post(self.mes_endpoint, json=payload, verify=verify)
        except Exception as ex:
            log.error(str(ex))
            return

        if not response.ok:
            log.error('Failed request to MES')
            return
        return response.json()

class WorkOderDataHandler(ExecutiveHandler):
    """
    This endpoint recieves data from UI inputs
    """

    def initialize(self, **kwargs):
        self.tool = kwargs["tool"]

    def get(self):
        self.write({
            'work_order_number': self.tool.work_order_number,
            'route_qualifier_name': self.tool.route_qualifier_name,
            'route_qualifier_value_options': self.tool.route_qualifier_value_options,
            'route_qualifier_value': self.tool.route_qualifier_value
            })

    def post(self):
        work_order_number = self.json_args.get('workOrderNumber')
        route_qualifier_value = self.json_args.get('routeQualifierValue')

        mes_response = self.tool.send_work_order_payload_to_mes(work_order_number, route_qualifier_value)
        if not mes_response:
            self.set_status(status_code=400, reason='Failed request to MES')
            return

        valid = mes_response.get('Valid')

        if valid:
            self.tool.work_order_number = work_order_number
            self.tool.route_qualifier_value = route_qualifier_value

            routing_data = {
                'work_order_number': self.tool.work_order_number,
                'route_qualifier_name': self.tool.route_qualifier_name,
                'route_qualifier_value': self.tool.route_qualifier_value
            }

            emit_event(InfoEvents.ROUTING_DATA_UPDATE, data_dict=routing_data)
            
            self.write({
                'valid': valid,
                'work_order_number': work_order_number,
                'route_qualifier_value': route_qualifier_value
                })
            return
        else:
            message = mes_response.get('ErrorMessage')
            self.tool.mes_response_message = message
            self.write({
                'valid': valid,
                'error_message': message
                })
            return

