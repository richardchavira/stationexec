# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import sys

import simplejson
from stationexec.logger import log
from stationexec.sequencer.utilities import evaluate_conditional, parse_result_condition, string_to_int, string_to_bool
from stationexec.utilities.uuidstr import get_uuid


class Result(object):
    def __init__(
        self,
        result,
        report_error,
        parent_operation,
        description="",
        system_configs=None,
        n_pos=None,
        n_up=1,
        n_up_operations=None,
    ):
        self._report_error = report_error
        self.parent = parent_operation
        self.id = result.get("id")
        if self.id is None:
            raise Exception("Result created with no 'id'")
        self.description = result.get('description', description)
        self.system_configs = system_configs
        self.type = result.get("type", "numeric")
        self.condition = result.get('condition')
        self.uuid = get_uuid()
        self.size = 0

        self._external_data = []
        self._result_is_processed = False
        self._display_value = None

        # Optional tag to relate the result to something specific like a serial number
        self._identifier = None

        if self.type not in self._get_valid_data_types():
            self._report_error(
                "Unknown result type '{0}' declared in result '{1}' of '{2}'".format(
                    self.type, self.id, self.parent
                )
            )

        self.dependencies = []
        if n_up_operations is None:
            n_up_operations = []

        # Consider result_value as operand1
        # if using <, >, ==, etc, only operand 2 will be populated (result_value < operand2)
        # however, if using 'inrange' or '!inrange', operand3 will exist
        #   result_value inrange operand2, operand3
        self.result_value = None
        self.operand2 = None
        self.operand3 = None
        self.operator = None
        # If conditional, result will be contribute to test pass/fail and will be evaluated against
        # its conditions. If it is not, then it will be considered a data item to be simply stored
        # in the database. If 'do_store' is False, then the value will be cached only for usage
        # in the sequence.
        self.is_result = "condition" in result and self.type in ["numeric", "boolean"]
        self.do_store = result.get("store", True)

        self.evaluate_conditional_operators()
        
        if n_up <= 1:
            # Not in n_up mode - Clean up operation references in case there is reference to a
            # specific n_up operation name
            for key in self._external_data:
                if key["source"] not in ["_config", "_constant"]:
                    key["source"] = key["source"].split("__")[0]

        to_remove = []
        for idx, data in enumerate(self._external_data):
            if data["source"] in n_up_operations:
                to_remove.append(idx)
                if n_pos is not None:
                    # If this operation is n_up, use the same n_up tag
                    new_data = dict(data)
                    new_data["source"] = "{0}__{1}".format(data["source"], n_pos)
                    self._external_data.append(new_data)
                else:
                    # Non-specific reference to an n-up operation - unclear which to choose
                    self._report_error(
                        "Standard result referencing data in an n_up operation - "
                        "unclear which value to choose"
                    )
        for idx in to_remove:
            del self._external_data[idx]

        self.dependencies = [
            key["source"]
            for key in self._external_data
            if key["source"] not in ["_config", "_constant"]
        ]

    def __str__(self):
        return "<Result id='{0}'>".format(self.id)

    def __repr__(self):
        return "<Result id='{0}'>".format(self.id)

    def refresh(self):
        self.uuid = get_uuid()
        self.size = 0
        self.result_value = None
        self._result_is_processed = False
        self._display_value = None

    def _evaluate(self, storage_cache=None):
        if not self._result_is_processed:
            return False
        
        self.evaluate_conditional_operators()
        
        if self.is_result:
            if storage_cache:
                self.update_external_data(storage_cache)
            conditionals_valid = True
            # Ensure that the conditional values are valid for comparison - int, float, bool
            for op, op_name in zip(
                [self.result_value, self.operand2, self.operand3],
                ["result_value", "operand2", "operand3"],
            ):
                if op is None:
                    continue
                if type(op) not in [int, float, bool]:
                    conditionals_valid = False
                    log.error(
                        "Unsupported operand type in result condition: '{0}' '{1}'".format(
                            op_name, type(op)
                        )
                    )
            if conditionals_valid:
                return evaluate_conditional(
                    self.operator, self.result_value, self.operand2, self.operand3
                )
            else:
                return False
        else:
            return True

    def get_value(self):
        return self.result_value, self.id

    # def get_display_value(self):
    #     return self._display_value

    def get_status(self):
        return {
            "uuid": self.uuid,
            "name": self.id,
            "identifier": self._identifier,
            "description": self.description,
            "value": self.result_value,
            "passing": self._evaluate(),
            # The value itself is considered Operand 1; result < operand2 or
            # result inrange(op2, op3)
            "operator": self.operator,
            "operand2": self.operand2,
            "operand3": self.operand3,
            "mimetype": self.type,
            "size": self.size,
            "is_result": self.is_result,
            "parent": self.parent,
            "is_processed": self._result_is_processed
        }

    def get_name(self):
        return self.id

    def store_result(self, result):
        if self.type is None and "type" in result:
            if result["type"] not in self._get_valid_data_types():
                raise Exception(
                    "Unknown result type '{0}' in result '{1}' of '{2}' "
                    "stored during sequence".format(
                        result["type"], self.id, self.parent
                    )
                )
            self.type = result["type"]

        self._identifier = result.get("identifier")
        
        # condition specified at runtime in Operation.save_result
        if result.get('condition'):
            self.condition = result.get('condition')
            self.type = result.get('type')
            self.is_result = True
        if result.get('description'):
            self.description = result['description']

        try:
            self.result_value = self._type_coercion(result["value"])
        except Exception as e:
            raise Exception(
                "Unable to coerce value '{0}' of result '{1}' to "
                "type '{2}' in operation '{3}': {4}".format(
                    result["value"], self.id, self.type, self.parent, e
                )
            )

        if not self.is_result:
            # Get size of the data
            self.size = sys.getsizeof(self.result_value)

        self._result_is_processed = True

    def _type_coercion(self, value):
        if self.type == "numeric":
            typed_value = string_to_int(value)
            if not typed_value:
                value = float(value)
            else:
                value = typed_value
        elif self.type == "boolean":
            value = int(string_to_bool(value))
        elif self.type == "binary":
            pass
        elif self.type in ["json", "application/json"]:
            if isinstance(value, str):
                # Assume the data is already a json string and don't process
                pass
            elif isinstance(value, dict) or isinstance(value, list):
                # Dump the dictionary to JSON string
                value = simplejson.dumps(value)
        elif self.type in ["zip", "application/zip"]:
            pass
        elif self.type == "floating-point":
            pass
        elif self.type == "application/pdf":
            pass
        elif self.type in ["text/plain", "text/csv"]:
            pass
        elif self.type in ["image/jpeg", "image/png"]:
            pass
        elif self.type in ["audio/mpeg", "audio/wav", "video/mp4"]:
            pass
        elif self.type in ["None", None]:
            self.type = "None"
        else:
            raise Exception("Unknown result type found: {0}".format(self.type))

        return value

    @staticmethod
    def _get_valid_data_types():
        return [
            "numeric",
            "boolean",
            "binary",
            "json",
            "application/json",
            "zip",
            "application/zip",
            "floating-point",
            "application/pdf",
            "text/plain",
            "text/csv",
            "image/jpeg",
            "image/png",
            "audio/mpeg",
            "audio/wav",
            "video/mp4",
            "None",
        ]

    def did_pass(self, storage_cache):
        return self._evaluate(storage_cache)

    def update_external_data(self, storage_cache):
        for item in self._external_data:
            if item["source"] in storage_cache:
                item["value"] = storage_cache[item["source"]].get(item["external_key"])

        # Set the storage cache data parameters into the result
        for val in self._external_data:
            key = val["local_key"]
            value = val["value"]
            if key.startswith("_data::"):
                key = key.split("::", 1)[1]
            setattr(self, key, value)

    def get_external_data(self):
        public_external_data = []
        for key in self._external_data:
            if key["source"] not in ["_config", "_constant"]:
                public_external_data.append((key["source"], key["external_key"]))
        return public_external_data

    def evaluate_conditional_operators(self):
        if self.is_result and self.system_configs is not None:
            try:
                self.operator, op2, op3 = parse_result_condition(
                    self.condition, self.system_configs
                )
            except KeyError as e:
                self._report_error(
                    "Result '{0}' missing _config data in condition: key error {1}".format(
                        self.id, e
                    )
                )
            except ValueError as e:
                if "inrange" in self.condition:
                    self._report_error(
                        "Result condition not formatted correctly - "
                        "inrange requires two arguments separated by comma - 'inrange 10, 20'. "
                        "Found '{0}' instead. Error: {1}".format(
                            self.condition, e
                        )
                    )
                else:
                    self._report_error(
                        "Result condition not formatted correctly - no loop parameters given in '{0}'."
                        "Error: {1}".format(self.condition, e)
                    )
            else:
                self.operand2 = op2["value"]
                self.operand3 = op3["value"]
                self._external_data.append(op2)
                self._external_data.append(op3)

