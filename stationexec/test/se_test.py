# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import os
import sys
import tempfile
import unittest

se_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(se_path)
os.chdir(se_path)

from stationexec.utilities import config, result_references


class UtilitiesConfig(unittest.TestCase):
    def setUp(self):
        json_data = (
            b'{"http_port":8888,"db_host":"localhost","db_database":"stationexec",'
            b'"db_user":"stationexec","locale":"en_US","threads":1,"debug":1}'
        )
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(json_data)
        self.temp_file.close()

    def tearDown(self):
        os.unlink(self.temp_file.name)

    def test_get_all_paths(self):
        pass

    def test_format_name1(self):
        self.assertEqual(config.format_name("Formatted-Name")[0], "formatted_name")
        self.assertEqual(config.format_name("Formatted-Name")[1], "FormattedName")
        self.assertEqual(config.format_name("Formatted-Name")[2], "Formatted Name")

    def test_format_name2(self):
        self.assertEqual(
            config.format_name(" _ - * Formatted#*/--_ Name")[0], "formatted_name"
        )
        self.assertEqual(
            config.format_name(" _ - * Formatted#*/--_ Name")[1], "FormattedName"
        )
        self.assertEqual(
            config.format_name(" _ - * Formatted#*/--_ Name")[2], "Formatted Name"
        )

    def test_merge_config_data(self):
        pass

    def test_load_config1(self):
        self.assertEqual(
            config.load_config(self.temp_file.name),
            {
                'http_port': 8888,
                'db_host': 'localhost',
                'db_database': 'stationexec',
                'db_user': 'stationexec',
                'locale': 'en_US',
                'threads': 1,
                'debug': 1,
            },
        )

    def test_load_config2(self):
        # Path and File Name separate
        self.assertEqual(
            config.load_config(
                os.path.dirname(self.temp_file.name),
                os.path.split(self.temp_file.name)[1],
            ),
            {
                'http_port': 8888,
                'db_host': 'localhost',
                'db_database': 'stationexec',
                'db_user': 'stationexec',
                'locale': 'en_US',
                'threads': 1,
                'debug': 1,
            },
        )

    def test_load_config3(self):
        # Good Test
        self.assertEqual(
            config.load_config(self.temp_file.name),
            {
                'http_port': 8888,
                'db_host': 'localhost',
                'db_database': 'stationexec',
                'db_user': 'stationexec',
                'locale': 'en_US',
                'threads': 1,
                'debug': 1,
            },
        )

    def test_load_config4(self):
        # Malformed JSON (trailing comma)
        with open(self.temp_file.name, "w"):
            # Clear file
            pass
        with open(self.temp_file.name, "w") as f:
            f.write('{"http_port":8888,"db_host":"localhost","threads":1,"debug":1,}')
        self.assertRaises(Exception, config.load_config, self.temp_file.name)

    def test_remote_path_import(self):
        pass


class UtilitiesResultReferences(unittest.TestCase):
    def test_looks_like_result_reference1(self):
        self.assertFalse(result_references.looks_like_result_reference(None))

    def test_looks_like_result_reference2(self):
        self.assertFalse(
            result_references.looks_like_result_reference("non_ref_string")
        )

    def test_looks_like_result_reference3(self):
        self.assertTrue(
            result_references.looks_like_result_reference("OpRef:result_name")
        )

    def test_reference_parse_parts1(self):
        self.assertRaises(ValueError, result_references.reference_parse_parts, None)

    def test_reference_parse_parts2(self):
        self.assertRaises(ValueError, result_references.reference_parse_parts, 123)

    def test_reference_parse_parts3(self):
        self.assertRaises(ValueError, result_references.reference_parse_parts, "ABC")

    def test_reference_parse_parts4(self):
        self.assertEqual(
            result_references.reference_parse_parts("OpRef:result_name"),
            ["OpRef", "result_name"],
        )

    def test_operation_has_result1(self):
        self.assertFalse(
            result_references.operation_has_result({}, "OpRef:result_name")
        )

    def test_operation_has_result2(self):
        self.assertFalse(
            result_references.operation_has_result(
                {"OpRef": {"operation_results": [{"name": "not_result_name"}]}},
                "OpRef:result_name",
            )
        )

    def test_operation_has_result3(self):
        self.assertTrue(
            result_references.operation_has_result(
                {"OpRef": {"operation_results": [{"name": "result_name"}]}},
                "OpRef:result_name",
            )
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
