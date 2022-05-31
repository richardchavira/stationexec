# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import argparse
import os
import shutil
import sys

from tornado.template import Template

from stationexec.utilities.config import format_name, get_all_paths
from stationexec.utilities.path_utils import get_file_content


def generate_tool():
    """
    :return:
    """
    parser = argparse.ArgumentParser(description='Tool Generator')
    parser.add_argument("name", help="name of the tool")
    parser.add_argument("-t", "--type", help="(optional) type of generated tool. Choice of: async",
                        required=False, default=None)
    args, _ = parser.parse_known_args(sys.argv)

    given_name = args.name
    name, class_name, display_name = format_name(given_name)

    # Tool 'static' URL to access static folder would conflict with tool called static
    if name == "static":
        raise Exception("Cannot create Tool 'static' - this is a reserved name")

    if args.type == "async":
        main_file = "async_tool_template.py"
    else:
        main_file = "tool_template.py"

    template_path = os.path.join(get_all_paths()["module_root"],
                                 "cli", "templates", "tool_template")
    item_path = os.path.join(get_all_paths()["app_root"], "tools", name)

    # Create directory for the item itself inside the specified parent folder
    if create_folder(item_path):
        print("Tool '{0}' already exists at path {1}".format(name, item_path))
        return
    # Create a UI folder inside the item folder
    create_folder((os.path.join(item_path, "ui")))

    replacement = {
        "tool_type": name,
        "tool_class": class_name,
        "tool_name": display_name,
    }

    files = {
        main_file: "{0}.py".format(name),
        os.path.join("ui", "index.html"): os.path.join("ui", "index.html"),
        "__init__.py": "__init__.py",
    }
    for template_file in files:
        from_template = os.path.join(template_path, template_file)
        for_new_tool = os.path.join(item_path, files[template_file])
        create_from_template(from_template, replacement, for_new_tool)

    print("'{0}' tool created at '{1}'".format(name, item_path))


def generate_station():
    """
    :return:
    """
    parser = argparse.ArgumentParser(description='Station Generator')
    parser.add_argument("name", help="name of the station")
    args, _ = parser.parse_known_args(sys.argv)

    given_name = args.name
    name, class_name, display_name = format_name(given_name)

    template_path = os.path.join(get_all_paths()["module_root"],
                                 "cli", "templates", "station_template")
    item_path = os.path.join(get_all_paths()["app_root"], "stations", name)

    # Create directory for the item itself inside the specified parent folder
    if create_folder(item_path):
        print("Station '{0}' already exists at path {1}".format(name, item_path))
        return
    # Create a UI folder inside the item folder
    try:
        create_folder((os.path.join(item_path, "ui")))

        replacement = {
            "station_type": name,
            "station_class": class_name,
            "station_name": display_name,
        }

        files = {
            "station.py": "station.py",
            "operations.py": "operations.py",
            "operations.json": "operations.json",
            "tool_manifest.json": "tool_manifest.json",
            os.path.join("ui", "index.html"): os.path.join("ui", "index.html"),
            "__init__.py": "__init__.py",
        }
        for template_file in files:
            from_template = os.path.join(template_path, template_file)
            for_new_tool = os.path.join(item_path, files[template_file])
            create_from_template(from_template, replacement, for_new_tool)

        print("'{0}' station created at '{1}'".format(name, item_path))
    except Exception:
        shutil.rmtree(item_path, ignore_errors=True)
        raise


def create_folder(location):
    """

    :param location:
    :return: True if folder already exists, False if new folder created
    """
    if not os.path.exists(location):
        os.makedirs(location)
        return False
    else:
        return True


def create_from_template(file_name, repl, new_name):
    content = get_file_content(file_name)
    src = Template(content)
    contents = src.generate(**repl)
    contents = contents.decode("utf-8")

    with open(new_name, "w") as output:
        output.write(contents)


"""
# For reference in case it becomes useful one day - implement prompts with Click

def interactive_tool():
    kwargs = {}

    tool_name = prompt_for_text('What is the name of the tool?')
    tool_type = prompt_for_list('What type of tool is this?', ['Default', 'Async', 'Camera'])
    if tool_type == 'async':
        async_type = prompt_for_list('What type of async tool?', ['Serial', 'TCP'])
        if async_type == 'serial':
            kwargs['com'] = prompt_for_text('Which com port do you want to use?',
                                            'COM1' if os.name == 'nt' else '/dev/ttyUSB0')
            kwargs['baud'] = prompt_for_text('Enter the connection baud rate:', '115200')
        else:
            kwargs['host'], kwargs['port'] = prompt_for_text('Enter the IP address and port for the connection:',
                                                             '127.0.0.1:8000').split(':')
        delimiter = prompt_for_list('Which is the end of line delimiter for the communication?',
                                    ['\\r', '\\n', '\\r\\n',
                                     '\\0', 'none', 'other'],
                                    filter=None)
        if delimiter == 'none':
            kwargs['delimiter'] = None
        elif delimiter == 'other':
            kwargs['delimiter'] = prompt_for_text('Enter the end of line delimiter for the communication:')
        else:
            kwargs['delimiter'] = delimiter

    for _idx in range(100):
        arg = prompt_for_text('Enter config parameters as key:value (e.g. baud_rate:115200). '
                              '(Enter to skip)')
        if arg == '':
            break
        else:
            k, v = arg.split(':')
            kwargs[k] = v

    return tool_name, tool_type, kwargs
"""
