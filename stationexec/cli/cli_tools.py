# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
CLI Utilities
"""
import argparse
import os
import shutil
import sys

import stationexec
from stationexec.cli.generate import generate_tool, generate_station
from stationexec.cli.launcher import package
from stationexec.main import Main
from stationexec.toolbox.tool_utilities import (
    load_tool_object,
    list_all_available_tools,
    ToolNotFound,
    build_package,
    clean_old_editable_installs,
)
from stationexec.utilities import config
from stationexec.utilities.colors import Colors
from stationexec.utilities.path_utils import copy_file, copy_tree


def cli_hello():
    """
    CLI utility to run the 'hello_prpl' demo station

    :return:
    """
    (
        default_app_root,
        _log_folder,
        _config_folder,
        _data_folder,
    ) = config.get_default_paths()
    if not os.path.exists(default_app_root):
        print("StationExec setup not complete - run 'se-setup' to finish setup")
        return

    try:
        port = int(sys.argv[1])
    except Exception:
        port = 8888
    print("View UI at http://localhost:{0}".format(port))

    sys.argv = []
    sys.argv.append("hello_prpl")
    sys.argv.append("-p")
    sys.argv.append(str(port))
    sys.argv.append("-d")
    sys.argv.append("3")

    main = Main()
    main.start()


def cli_setup(force=False, silent=False, refresh_install=False, alt=None):
    """
    :return:
    """
    if not (force is True or alt is not None):
        # Allow for direct call or call with vargs - ignore argparse if direct call args used
        parser = argparse.ArgumentParser(description="StationExec Setup")
        parser.add_argument(
            "--force",
            help="Overwrite installation if it exists",
            action="store_true",
            required=False,
        )
        parser.add_argument(
            "--alt",
            help="Create installation in different directory",
            type=str,
            default="",
            required=False,
        )
        args, _ = parser.parse_known_args(sys.argv[1:])

        force = args.force
        alt = args.alt

    if alt:
        config._set_alternate_app_path(os.path.abspath(alt))

    # Manually build app and module root paths - config file path method changes working directory,
    # which can mess with the target folder, making it difficult to delete
    (
        default_app_root,
        log_folder,
        config_folder,
        data_folder,
    ) = config.get_default_paths()
    module_root_path = os.path.dirname(os.path.abspath(stationexec.__file__))

    template_path = os.path.join(module_root_path, "cli", "templates", "new_project")
    if not os.path.exists(default_app_root):
        # Folder does not exist - copy starter folders into it
        copy_tree(template_path, default_app_root)
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)
        if not os.path.exists(data_folder):
            os.makedirs(data_folder)
    elif refresh_install:
        # Regenerate installation, but preserve the data and log folders
        to_refresh = [
            "__init__.py",
            "se-launch.py",
            "se-tool.py",
            "stations",
            "tools",
            "config",
        ]
        for target in to_refresh:
            in_template = os.path.join(template_path, target)
            in_installation = os.path.join(default_app_root, target)
            if in_installation.endswith("py"):
                if os.path.exists(in_installation):
                    os.remove(in_installation)
                copy_file(in_template, in_installation)
            else:
                shutil.rmtree(in_installation, ignore_errors=True)
                copy_tree(in_template, in_installation)
    elif os.path.exists(default_app_root):
        if not force:
            if not silent:
                print(
                    "Folder already exists at '{0}'. Run again with '--force' flag to overwrite".format(
                        default_app_root
                    )
                )
            return
        # Force install - remove old install
        shutil.rmtree(default_app_root, ignore_errors=True)
        # Copy starter folders in
        copy_tree(template_path, default_app_root)
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)
        if not os.path.exists(data_folder):
            os.makedirs(data_folder)


def cli_start():
    """
    CLI utility to start stationexec

    :return:
    """
    (
        default_app_root,
        _log_folder,
        _config_folder,
        _data_folder,
    ) = config.get_default_paths()
    if not os.path.exists(default_app_root):
        print("StationExec setup not complete - run 'se-setup' to finish setup")
        return

    sys.argv = sys.argv[1:]
    if len(sys.argv) < 1:
        # No station provided - launch help dialog
        sys.argv.append("--help")
    main = Main()
    main.start()
    sys.exit(1)


def cli_station():
    try:
        arg = sys.argv[1]
    except Exception:
        arg = "list"

    if arg not in ["gen", "generate", "launch", "list", "build"]:
        print("Unknown 'station' argument '{0}'".format(arg))
        return

    if arg in ["gen", "generate"]:
        sys.argv = sys.argv[2:]
        if len(sys.argv) == 0:
            sys.argv.append("--help")
        generate_station()
    elif arg == "launch":
        # Same as se-start - call se-start - remove first item from sys arguments
        # to satisfy se-start's expectations
        sys.argv = sys.argv[1:]
        cli_start()
    elif arg == "list":
        stations = config.get_modules_in_directory(config.get_all_paths()["stations"])
        stations = [
            "{0}{1}{2}".format(Colors.OKGREEN, station, Colors.ENDC)
            for station in stations
        ]
        print(
            "Available Stations (launch station with 'se-start <station name>'): \n - {0}".format(
                "\n - ".join(stations)
            )
        )
    elif arg == "build":
        if os.name != "nt":
            print("Station building is Windows only at this time.")
            return
        sys.argv = sys.argv[2:]
        if len(sys.argv) == 0:
            sys.argv.append("--help")
        parser = argparse.ArgumentParser(description="Station EXE Builder")
        parser.add_argument("station", help="Station to package into an executable")
        parser.add_argument(
            "--debug",
            help="Maintain the intermediate build files for debugging builds",
            action="store_true",
        )
        args, _ = parser.parse_known_args(sys.argv)
        package.main(args.station, args.debug)


def cli_tool():
    try:
        arg = sys.argv[1]
    except Exception:
        arg = "list"

    # TODO if arg == "help":
    if arg not in ["gen", "generate", "launch", "list", "build"]:
        print("Unknown 'se-tool' argument '{0}'".format(arg))
        return

    if arg in ["gen", "generate"]:
        sys.argv = sys.argv[2:]
        if len(sys.argv) == 0:
            sys.argv.append("--help")
        generate_tool()
    elif arg == "launch":
        sys.argv = sys.argv[2:]
        if len(sys.argv) == 0:
            sys.argv.append("--help")
        _cli_tool_launcher()
    elif arg == "list":
        clean_old_editable_installs()
        external, internal, packages = list_all_available_tools()
        external = [
            "{0}{1}{2}".format(Colors.OKGREEN, tool, Colors.ENDC) for tool in external
        ]
        internal = [
            "{0}{1}{2}".format(Colors.WARNING, tool, Colors.ENDC) for tool in internal
        ]
        packages = [
            "{0}{1}{2}".format(Colors.OKBLUE, tool, Colors.ENDC) for tool in packages
        ]

        packaged_text = Colors.OKBLUE + "packaged" + Colors.ENDC + " | "
        external_text = Colors.OKGREEN + "external" + Colors.ENDC + " | "
        internal_text = Colors.WARNING + "internal" + Colors.ENDC

        print(
            "Available Tools (launch tool tester with 'se-tool launch <tool name>'): \n "
            " {1} {2} {3} \n - {0}".format(
                "\n - ".join(packages + external + internal),
                packaged_text,
                external_text,
                internal_text,
            )
        )
    elif arg == "build":
        sys.argv = sys.argv[2:]
        if len(sys.argv) == 0:
            sys.argv.append("--help")
        parser = argparse.ArgumentParser(description="Tool Package Builder")
        parser.add_argument("tool", help="Tool to package into distributable wheel")
        parser.add_argument(
            "--debug",
            help="Maintain the intermediate build files for debugging builds",
            action="store_true",
        )
        parser.add_argument(
            "-e",
            "--dev",
            help="Install as editable package for development "
            "(links directly to source) - no wheel output",
            action="store_true",
        )
        args, _ = parser.parse_known_args(sys.argv)
        build_package(args.tool, args.debug, args.dev)


def cli_which():
    """
    Report the installation path of stationexec. C:\\stationexec on Windows, ~/stationexec on Linux

    Invoked from command line after installation via 'se-which'

    :return:
    """
    (
        default_app_root,
        _log_folder,
        _config_folder,
        _data_folder,
    ) = config.get_default_paths()
    if not os.path.exists(default_app_root):
        print("StationExec setup not complete - run 'se-setup' to finish setup")
        return

    try:
        print(config.get_all_paths()["app_root"])
    except Exception as e:
        print(e)


def _cli_tool_launcher():
    """
    CLI utility to launch tools

    :return:
    """
    from stationexec.toolbox.tool_launch import ToolLaunch

    app_root = config.get_all_paths()["app_root"]
    if not os.path.exists(app_root):
        print("StationExec setup not complete - run 'se-setup' to finish setup")
        return

    parser = argparse.ArgumentParser(description="Tool Launcher")
    parser.add_argument("tool", help="Tool to launch")
    parser.add_argument(
        "-b",
        "--browser",
        help="Open new browser tab on tool launch",
        action="store_true",
    )
    parser.add_argument(
        "-l",
        "--location",
        help="Specify location if multiples of same name tool exist",
        required=False,
        default=None,
    )
    parser.add_argument(
        "--kwargs",
        help="'key:value' pair of configuration data - " "add as many as desired",
        required=False,
        default=None,
        action="append",
    )
    args, _ = parser.parse_known_args(sys.argv)

    try:
        module = load_tool_object(args.tool, args.location)
    except ToolNotFound as e:
        print("Unable to load tool '{0}' for launch: {1}".format(args.tool, e))
        return

    tu = ToolLaunch()
    name, class_name, disp = config.format_name(args.tool)

    # Load the tool module
    configurations = module.default_configurations

    tool_config = tu.build_tool_dict(
        args.tool, disp, "{0}_1".format(args.tool), configurations
    )
    version = "unknown" if not hasattr(module, "version") else module.version
    tool_config["version"] = version

    tool_class = getattr(module, class_name)
    tu.tool_setup(tool_class, tool_config)
    tu.tool_run(port=8888, browser=args.browser)


if __name__ == "__main__":
    cli_tool()
