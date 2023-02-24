# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
Config.py contains helpers for loading configuration files and getting the correct
 paths and parameters for navigating the program.
"""

import os
import re
import sys
from importlib import util, reload

import pkg_resources
import simplejson
import stationexec
from stationexec.logger import log
from stationexec.utilities.path_utils import list_dir, is_dir, exists

_SYSTEM_CONFIG_FILE_NAME = "stationexec.json"
_DEFAULT_STATION_IDENTITY = "Default"

_system_config_data = None
_system_paths = None
_station_identity = _DEFAULT_STATION_IDENTITY
_alt_home_path = None


class RootDoesNotExist(Exception):
    pass


def set_station_identity(identity):
    global _station_identity
    if _station_identity == _DEFAULT_STATION_IDENTITY:
        _station_identity = identity


def _set_alternate_app_path(path):
    global _alt_home_path
    if _alt_home_path is None:
        path = os.path.abspath(path)
        if not os.path.basename(path) == "stationexec":
            path = os.path.join(path, "stationexec")
        _alt_home_path = path


def get_system_config():
    global _system_config_data
    if _system_config_data is None:
        _root, _log, config_path, _data = get_default_paths()
        try:
            _system_config_data = load_config(
                os.path.join(config_path, _SYSTEM_CONFIG_FILE_NAME)
            )
        except Exception as e:
            # Unable to load system configuration file - try again later
            log.exception("Cannot load system configuration file", e)
    return _system_config_data


def get_all_paths():
    """
    Find and cache all important paths for stationexec

    N.B. Changes the working directory to the discovered app root path

    :return:
    """
    global _system_paths
    global _station_identity
    if _system_paths is None:
        _cache_data = True
        config_paths = {}
        # StationExec Module
        module_root = os.path.dirname(os.path.abspath(stationexec.__file__))
        config_paths["module_root"] = module_root
        # Default App Root, Log Folder, Config File
        default_app_root, log_folder, config_folder, data_folder = get_default_paths()
        config_paths["app_root"] = default_app_root
        config_paths["log_folder"] = log_folder
        config_paths["config_folder"] = config_folder
        config_paths["config_file"] = os.path.join(
            config_folder, _SYSTEM_CONFIG_FILE_NAME
        )
        config_paths["data_folder"] = data_folder
        # Application Root
        try:
            os.chdir(config_paths["app_root"])
        except Exception as e:
            raise RootDoesNotExist(
                "Missing root folder '{0}' - run 'se-setup' to fix: {1}".format(
                    config_paths["app_root"], str(e)
                )
            )
        # Station
        if _station_identity == _DEFAULT_STATION_IDENTITY:
            # Station identity has not been set - recalculate paths next time in case it is set
            _cache_data = False
        config_paths["stations"] = os.path.join(config_paths["app_root"], "stations")
        config_paths["station"] = os.path.join(
            config_paths["stations"], _station_identity
        )
        config_paths["tool_manifest"] = os.path.join(
            config_paths["station"], "tool_manifest.json"
        )
        config_paths["station_file"] = os.path.join(
            config_paths["station"], "station.py"
        )
        config_paths["operation_defs"] = os.path.join(
            config_paths["station"], "operations.py"
        )
        config_paths["operation_config"] = os.path.join(
            config_paths["station"], "operations.json"
        )
        # Tools
        config_paths["tools_internal"] = os.path.join(module_root, "built_in")
        # if os.path.exists(os.path.join(config_paths["station"], "tools")):
        config_paths["tools_station_internal"] = os.path.join(config_paths["station"], "tools")
        config_paths["tools_external"] = os.path.join(config_paths["app_root"], "tools")
        # UI
        config_paths["ui_folder"] = os.path.join(module_root, "ui")
        config_paths["default_ui_folder"] = os.path.join(module_root, "ui")

        if os.path.exists(os.path.join(config_paths["station"], "config.json")):
            config_paths['station_config'] = os.path.join(
                config_paths["station"], "config.json"
            )
            station_config = load_config(config_paths['station_config'])
            if "ui_replacement" in station_config:
                config_paths["ui_folder"] = station_config["ui_replacement"]

        sys.path.append(config_paths["stations"])
        sys.path.append(config_paths["tools_internal"])
        sys.path.append(config_paths["tools_external"])

        if _cache_data:
            _system_paths = config_paths
        else:
            return config_paths
    return _system_paths


def verify_paths_exist():
    does_not_exist = []
    paths = get_all_paths()
    for path in paths:
        real_path = paths[path]
        if not exists(real_path):
            does_not_exist.append(real_path)
    if len(does_not_exist) > 0:
        raise Exception(
            "Missing required stationexec items - please run 'se-setup' to fix"
            " to repair. \nMissing: \n- {0}".format("\n- ".join(does_not_exist))
        )


def get_default_paths():
    app_root_path = find_app_root()
    log_path = os.path.join(app_root_path, "log")
    config_path = os.path.join(app_root_path, "config")
    data_path = os.path.join(app_root_path, "data")
    return app_root_path, log_path, config_path, data_path


def find_app_root():
    global _alt_home_path
    if os.name == "nt":
        root_path = os.path.abspath(os.sep)
    else:
        root_path = os.path.expanduser("~")

    if _alt_home_path:
        return _alt_home_path
    else:
        return os.path.join(root_path, "stationexec")


def format_name(name_in):
    """
    Reformat name_in to adhere to StationExec convention
    - lowercase, separated by underscore - and generate a class name
    and display name version

    e.g. name_in = Strong-bad
         name_out = strong_bad
         class_name = StrongBad
         display_name = Strong Bad

    :param str name_in: string name to be reformatted
    :return: name_out, class_name, display_name
    :rtype: tuple
    """
    name_temp = re.sub("[^A-Za-z0-9]+", "_", name_in).lower().split("_")
    if name_temp[0] == "":
        # Remove leading underscore
        del name_temp[0]
    name_out = "_".join(name_temp)
    class_name = "".join(x.capitalize() for x in name_out.split("_"))
    display_name = " ".join(x.capitalize() for x in name_out.split("_"))

    return name_out, class_name, display_name


def merge_config_data(input_arguments):
    """
    Merge data from command line arguments, input configuration file, and default
    system configuration file into one config dictionary

    :param input_arguments:
    :return:
    """
    # TODO Consider making config data able to be accessed globally - would be much easier
    #  maybe separate from the database configs so passwords not available
    command_line_config = vars(input_arguments)
    system_config = get_system_config()
    input_file_config = {}

    input_config_file_path = command_line_config["file"]
    if input_config_file_path is None:
        input_config_file_path = os.path.join(get_all_paths()["station"], "config.json")
    if os.path.exists(input_config_file_path):
        input_file_config = load_config(input_config_file_path)

    se_config_data = system_config.copy()
    for data in command_line_config:
        se_config_data[data] = command_line_config[data]
    for data in input_file_config:
        se_config_data[data] = input_file_config[data]

    # Store https cert data separately
    cert = se_config_data.get("https_cert", None)
    key = se_config_data.get("https_key", None)
    if cert is None or key is None:
        se_config_data["https_data"] = None
    else:
        se_config_data["https_data"] = {"certfile": cert, "keyfile": key}

    # Stare database cert data separately
    db_data = {
        "host": se_config_data.get("db_host", None),
        "database": se_config_data.get("db_database", None),
        "user": se_config_data.get("db_user", None),
        "password": se_config_data.get("db_password", None),
        "ca": se_config_data.get("db_ca", None),
        "cert": se_config_data.get("db_cert", None),
        "key": se_config_data.get("db_key", None),
    }
    se_config_data["db_data"] = {k: v for k, v in db_data.items() if v is not None}

    # Setup station names (in case they are not defined)
    name, _class_name, display_name = format_name(se_config_data["station"])
    if se_config_data["name"] is None:
        se_config_data["name"] = display_name
    if se_config_data["instance"] is None:
        se_config_data["instance"] = "{0}_1".format(name)

    if os.getenv("__SE_EXE_PATH__") is None:
        os.environ["__SE_EXE_PATH__"] = sys.executable
    se_config_data["is_executable"] = os.getenv("__SE_EXE__") == "True"
    se_config_data["exe_path"] = os.getenv("__SE_EXE_PATH__")
    se_config_data["is_zip"] = ".zip" in os.path.abspath(__file__)

    return se_config_data


def load_config(config_file_path, config_file_name=None):
    # type: (str, str) -> dict
    """
    Load the specified JSON config_file_name from the specified config_file_path

    Note: carriage return characters are removed from the input

    :param str config_file_path: file path
    :param str config_file_name: [optional] name of file located at config_file_path, to append
        to end of path

    :return: JSON read from files
    :rtype: dict

    :raise: simplejson.JSONDecodeError on JSON syntax errors
    """
    file_to_load = config_file_path
    if config_file_name is not None:
        file_to_load = os.path.join(config_file_path, config_file_name)

    log.debug(2, "Loading config file {0}".format(file_to_load))
    with open(file_to_load) as main_config:
        config_json = main_config.read().replace("\r", "")
        try:
            config_dict = simplejson.loads(config_json)
            return config_dict
        except Exception as e:
            log.error("Failed to load config file {0}: {1}".format(file_to_load, e))
            raise


def remote_path_import(module_path, reload_mod=False):
    """
    Programmatically import module at a particular path

    :param str module_path: path to module to import
    :param bool reload_mod: whether to reload the package on import (if loading mod again)

    :return: Imported module object
    :rtype: module
    """
    if os.path.isdir(module_path):
        if module_path not in sys.path:
            sys.path.append(module_path)
        module_name = os.path.basename(module_path)
        module_path = os.path.join(module_path, module_name + ".py")
    else:
        module_name = os.path.splitext(os.path.basename(module_path))[0]

    # Import the package
    # https://docs.python.org/3.7/library/importlib.html#importing-a-source-file-directly
    spec = util.spec_from_file_location(module_name, module_path)
    _module = util.module_from_spec(spec)
    spec.loader.exec_module(_module)

    if reload_mod:
        # Force the module to be reloaded - in case code changed and the old version is cached
        reload(_module)
    return _module


def get_modules_in_directory(directory):
    # Module folders must be in the path for this to work - default tool and station folders
    #  are added above in get_all_paths
    modules_found = []
    path = os.path.abspath(directory)
    all_folders = [
        folder for folder in list_dir(path) if is_dir(os.path.join(path, folder))
    ]
    for folder in all_folders:
        try:
            mod = util.find_spec(folder)
            if mod is None or mod.loader is None:
                raise ModuleNotFoundError()
            modules_found.append(folder)
        except (ImportError, FileNotFoundError):
            # Found a folder that is not a module
            pass
        except Exception as e:
            print(
                "Exception while processing package '{0}': {1}".format(folder, str(e))
            )
    return modules_found


def get_reqs(reqs):
    """
    Return list of tuples of all requirements of a package or list of packages. Input requirements must be the
        official name of the package and not the imported name (i.e. opencv-python rather than cv2 - this method
        will detect the secondary name)

    The tuple is (folder name, folder location, version) - so for a package that is just a file, the name is
        None and the location is the path to the file
    """
    paths_to_save = {}

    def get_req(target):
        try:
            package = pkg_resources.working_set.by_key[target.lower()]
        except KeyError:
            raise Exception(
                "Cannot find dependency - must be installed first: '{0}'".format(target)
            )
        else:
            name_list = [package.project_name]
            if os.path.exists(os.path.join(package.egg_info, "top_level.txt")):
                # If names are defined in top_level, they take precedence over the project name (usually case
                #  differences or name tweaks
                name_list = []
                with open(os.path.join(package.egg_info, "top_level.txt")) as f:
                    names = f.readlines()
                    for nm in names:
                        name_list.append(nm.strip())
            for name in name_list:
                # In case the name is to a deeper path - take the root only
                name = os.path.normpath(name).split(os.sep)[0]
                try:
                    pkg_version = pkg_resources.working_set.by_key[name.lower()].version
                except KeyError:
                    pkg_version = None
                if os.path.exists(os.path.join(package.location, name)):
                    paths_to_save[name] = (
                        name,
                        os.path.join(package.location, name),
                        pkg_version,
                    )
                elif os.path.exists(
                    os.path.join(package.location, "{0}.py".format(name))
                ):
                    paths_to_save[name] = (
                        None,
                        os.path.join(package.location, "{0}.py".format(name)),
                        pkg_version,
                    )
            for pkg in package.requires():
                get_req(pkg.name)

    if not isinstance(reqs, list):
        reqs = [reqs]
    for req in reqs:
        get_req(req)

    return list(paths_to_save.values())


if __name__ == "__main__":
    pths = get_reqs(["pyqtgraph", "cobs", "intelhex", "PyQt5"])
    for pt in pths:
        print(pt)
