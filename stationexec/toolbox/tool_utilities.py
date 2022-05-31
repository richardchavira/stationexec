# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import os
import shutil
import sys
from importlib import import_module, util, reload

import pkg_resources
from setuptools import setup
from stationexec.utilities import config, path_utils


class ToolNotFound(Exception):
    def __init__(self, message):
        super(ToolNotFound, self).__init__(message)


def load_tool_object(tool_name, location=None, reload_mod=False):
    """
    EAFP load tool by name

    :param tool_name:
    :param location:
    :param reload_mod:
    :return:
    """
    # Reformat name to adhere to stationexec standards
    module_name, class_name, display_name = config.format_name(tool_name)

    if location is None or location == "package":
        try:
            # Check if the tool package is installed
            mod = import_module("{0}.{0}".format(tool_name))
            if reload_mod:
                # Force the module to be reloaded - in case code changed and the old version is cached
                reload(mod)
            return mod
        except (AttributeError, ImportError, FileNotFoundError):
            raise ToolNotFound("Cannot locate tool '{0}'".format(module_name))
    else:
        try:
            if location == "external":
                return config.remote_path_import(
                    os.path.join(config.get_all_paths()["tools_external"], tool_name),
                    reload_mod)
            elif location == "internal":
                return config.remote_path_import(
                    os.path.join(config.get_all_paths()["tools_internal"], tool_name),
                    reload_mod)
            else:
                raise Exception("Unknown load location: {0}".format(location))
        except (ImportError, FileNotFoundError, AttributeError):
            raise ToolNotFound("Cannot locate tool '{0}' in '{1}'".format(module_name, location))


def get_tool_path(tool):
    try:
        packages = [entry_point.name for entry_point in pkg_resources.iter_entry_points("stationexec.tool")]
        if tool in packages:
            spec = util.find_spec("{0}.{0}".format(tool))
            return os.path.dirname(spec.origin)
        else:
            raise AttributeError
    except (AttributeError, ImportError):
        external = os.path.join(config.get_all_paths()["tools_external"], tool, tool + ".py")
        if os.path.exists(external):
            return os.path.dirname(external)
        else:
            internal = os.path.join(config.get_all_paths()["tools_internal"], tool, tool + ".py")
            if path_utils.exists(internal):
                return os.path.dirname(internal)
            else:
                raise ToolNotFound("Cannot locate tool '{0}'".format(tool))


def list_all_available_tools():
    """
    Get lists of all installed tools - internal, external, and stationexec packages

    :return:
    """
    external_tools = config.get_modules_in_directory(config.get_all_paths()["tools_external"])
    internal_tools = config.get_modules_in_directory(config.get_all_paths()["tools_internal"])
    packages = [entry_point.name for entry_point in pkg_resources.iter_entry_points("stationexec.tool")]

    return external_tools, internal_tools, packages


def clean_old_editable_installs():
    ex_eggs = [os.path.join(config.get_all_paths()["tools_external"], pth) for pth in
               os.listdir(config.get_all_paths()["tools_external"]) if pth.endswith("egg-info")]
    # Internal wheel building is disallowed for now
    # in_eggs = [os.path.join(config.get_all_paths()["tools_internal"], pth) for pth in
    #            os.listdir(config.get_all_paths()["tools_internal"]) if pth.endswith("egg-info")]
    # Pip doesn't clean up the egg-info folders out of tools after uninstalling editable installs
    _e, _i, packages = list_all_available_tools()
    # for pth in ex_eggs + in_eggs:
    for pth in ex_eggs:
        filename = os.path.splitext(os.path.basename(pth))[0]
        if filename not in packages:
            shutil.rmtree(pth, ignore_errors=True)


def build_package(package, debug=False, dev=False):
    tool_directory = config.get_all_paths()["tools_external"]
    clean_old_editable_installs()

    pip_name = "-".join(package.lower().split("_"))
    if dev:
        try:
            if pkg_resources.working_set.by_key[pip_name]:
                print("Package already installed as '{0}' - use pip to remove before creating new editable install"
                      .format(pip_name))
                return
        except KeyError:
            pass

    try:
        tool = load_tool_object(package, "external")
    except ToolNotFound:
        print("Unable to find and load tool '{0}' in '{1}'".format(package, tool_directory))
        return
    try:
        version = tool.version
    except AttributeError:
        version = "0.1"
    try:
        dependencies = tool.dependencies
    except AttributeError:
        dependencies = []

    # Change working directory to the external tool directory
    os.chdir(tool_directory)

    # Setup the manifest file to include everything in the tool folder except for compiled python files
    with open("MANIFEST.in", "w") as f:
        f.write("recursive-include {0} *\n".format(package))
        f.write("global-exclude *.py[co]\n")

    # Necessary information that normally would live in setup.py
    data = {
        "name": package,
        "version": version,
        "packages": [package],
        "include_package_data": True,
        "install_requires": dependencies,
        "classifiers": ["Framework :: stationexec"],
        "entry_points": {
            "stationexec.tool": ["{0} = {0}".format(package)]
        },
    }

    # Silence stderr - setuptools complains about this being an atypical setup (which it is by design)
    err = sys.stderr
    with open(os.devnull, "w") as f:
        sys.stderr = f

        sys.argv = [""]
        if not debug:
            sys.argv.append("--quiet")
        if dev:
            sys.argv.append("develop")
        else:
            # Build the package quietly, make it a binary distribution wheel, and universal (py2 py3)
            sys.argv.append("bdist_wheel")
            sys.argv.append("--universal")
        setup(**data)

    sys.stderr = err

    # Cleanup all temporary files
    if not debug:
        os.remove("MANIFEST.in")
        shutil.rmtree("build", ignore_errors=True)

    if dev:
        print("Editable installation created for '{0}' as '{1}'".format(package, pip_name))
    else:
        print("Wheel package created for '{0}' in {1}".format(
            package, os.path.join(tool_directory, "dist")))


if __name__ == "__main__":
    print(get_tool_path("cool"))
