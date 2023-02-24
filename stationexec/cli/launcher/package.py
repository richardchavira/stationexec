# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
from functools import wraps
from io import BytesIO
from socket import error
from timeit import default_timer
from threading import Thread
from zipfile import ZipFile, ZIP_DEFLATED

import simplejson
from stationexec.toolbox.tool_utilities import (
    get_tool_path,
    load_tool_object,
    ToolNotFound,
)
from stationexec.utilities import config
from stationexec.utilities.ioloop_ref import IoLoop
from tornado import gen
from tornado.httpclient import AsyncHTTPClient, HTTPError

PYTHON_VERSION_LOCATION = 34
PYTHON_LONG_VERSION_LOCATION = 35
MAIN_FILE_NAME_LOCATION = 36
MAIN_FILE_DATA_LOCATION = 37
LIB_NAME_LOCATION = 38
LIB_FILE_LOCATION = 39
PROGRAM_NAME_LOCATION = 42
PROGRAM_FILE_LOCATION = 43
PY_RESOURCE_HASH_NAME_LOCATION = 46
PY_RESOURCE_HASH_LOCATION = 47
PY_RESOURCE_ZIP_NAME_LOCATION = 48
PY_RESOURCE_ZIP_LOCATION = 49
PY_RESOURCE_COUNT_LOCATION = 50
PY_RESOURCE_FILES_START_LOCATION = 51
PY_RESOURCE_NAMES_START_LOCATION = 151

temp_folder = None
target_files = []

# Downloaded python zip stream
zip_file = None
python_version = "{0}.{1}".format(sys.version_info.major, sys.version_info.minor)
python_version_long = None
debug = True
exiting = False
is_64bits = sys.maxsize > 2 ** 32
python_embed_byte_version = "amd64" if is_64bits else "win32"


def write(name, data):
    global temp_folder
    name = "{0}".format(name)
    if os.path.exists(name):
        with open(os.path.join(temp_folder, name), "wb") as fw:
            with open(name, "rb") as fr:
                fw.write(fr.read())
    else:
        with open(os.path.join(temp_folder, name), "wb") as f:
            f.write(data)
    target_files.append(os.path.abspath(os.path.join(temp_folder, name)))


def timer():
    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            start = default_timer()
            ret = func(*args, **kwargs)
            end = default_timer()
            duration = end - start
            if debug:
                print("------- {0}: {1}s".format(func.__name__, duration))
            return ret

        return inner

    return decorator


def progress_spinner():
    global exiting
    prog = ["-", "\\", "|", "/"]
    i = 0
    while exiting is False:
        print(
            "\rWorking{0:<4} {1}{2}".format("." * (i % 4), prog[i % 4], " " * 2), end=""
        )
        i += 1
        time.sleep(0.25)
    print("\rComplete! {0:<10}".format(" " * 10), end="")


@timer()
def add_shim_file():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(current_dir, "shim.py"), "rb") as f:
        data = f.read()
    write(MAIN_FILE_NAME_LOCATION, b"launch.py")
    write(MAIN_FILE_DATA_LOCATION, data)


@timer()
def add_python_version_string():
    global python_version
    global python_version_long
    version = "python{0}".format("".join(python_version.split(".")))
    version_long = "python{0}_{1}".format(
        "".join(python_version_long.split(".")), "64" if is_64bits else "32"
    )

    write(PYTHON_VERSION_LOCATION, version.encode("utf8"))
    write(PYTHON_LONG_VERSION_LOCATION, version_long.encode("utf8"))


def get_cache_dir():
    cache_path = os.path.join(os.getenv("LOCALAPPDATA"), "stationexec", "cache")
    os.makedirs(cache_path, exist_ok=True)
    return cache_path


def get_latest_python_from_cache():
    global python_version
    cache = get_cache_dir()
    pythons = get_latest_python_in_string("".join(os.listdir(cache)))
    if len(pythons) > 0:
        v = os.path.join(
            cache,
            "python-{0}-embed-{1}.zip".format(pythons[0], python_embed_byte_version),
        )
        if os.path.exists(v):
            return v, pythons[0]
        else:
            return None, None
    else:
        return None, None


def get_latest_python_in_string(data):
    # Parse data and sort to find most up-to-date micro version of python related to current version
    # e.g. if user is running 3.6.3, find (if exists) 3.6.8
    src = "".join(data.split())
    versions = list(set(re.findall(r"\d\.\d+\.\d+", src)))
    versions.sort()
    target = "{0}.".format(python_version)
    matches = []
    for v in versions:
        if v.startswith(target):
            matches.append(v)
    matches.reverse()
    return matches


def download_embedded_python():
    py, version = get_latest_python_from_cache()
    if debug:
        global zip_file
        global python_version
        global python_version_long
        if py is None:
            python_version_long = "{0}.{1}".format(
                python_version, sys.version_info.micro
            )
            py_path = "python-{0}-embed-{1}.zip".format(
                python_version_long, python_embed_byte_version
            )
            current_dir = os.path.dirname(os.path.abspath(__file__))
            py = os.path.join(current_dir, py_path)
            if not os.path.exists(py):
                raise Exception(
                    "No offline python installations found - run in non-debug mode to download"
                )
        else:
            python_version_long = version
        with open(py, "rb") as f:
            zip_file = f.read()
    else:
        if sys.version_info >= (3, 5):
            import asyncio
            from tornado.platform.asyncio import AnyThreadEventLoopPolicy

            asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())

        IoLoop().init()
        IoLoop().current().spawn_callback(_download_python, py, version)
        IoLoop().current().start()


@timer()
@gen.coroutine
def _download_python(latest_cached_file=None, latest_version=None):
    global python_version
    global python_version_long
    global zip_file
    global exiting

    latest_filename = None
    if latest_cached_file is not None:
        latest_filename = os.path.basename(latest_cached_file)

    # Get latest python version
    base_url = "https://www.python.org/ftp/python/"
    try:
        response = yield AsyncHTTPClient().fetch(base_url)
    except (HTTPError, error) as e:
        if latest_cached_file is None:
            exiting = True
            raise Exception(
                "Unable to connect to internet to download Python: {0}".format(e)
            )
        else:
            print(
                "Cannot connect to internet to download latest Python - "
                "grabbing latest from cache: Python {0}".format(latest_version)
            )
            with open(latest_cached_file, "rb") as f:
                zip_file = f.read()
                python_version_long = latest_version
            IoLoop().current().spawn_callback(IoLoop().current().stop)
            return
    # Parse and sort to find most up-to-date micro version related to current version
    # e.g. if user is running 3.6.3, find and download 3.6.8 (3.6.9 windows embedded build doesn't exist)
    matches = get_latest_python_in_string(response.body.decode("utf8"))

    # Try to download the most up-to-date version of python that exists - walk backward through versions
    #  until one is found
    for v in matches:
        try:
            if (
                "python-{0}-embed-{1}.zip".format(v, python_embed_byte_version)
                == latest_filename
            ):
                # This version is found in the cache - no need to download
                with open(latest_cached_file, "rb") as f:
                    zip_file = f.read()
                    python_version_long = v
                IoLoop().current().spawn_callback(IoLoop().current().stop)
                return
            url = (
                "https://www.python.org/ftp/python/{0}/python-{0}-embed-{1}.zip".format(
                    v, python_embed_byte_version
                )
            )
            response = yield AsyncHTTPClient().fetch(url)
        except HTTPError:
            pass
        else:
            python_version_long = v
            break
    if python_version_long is None:
        raise Exception(
            "No suitable python embedded build found for Python{0}".format(
                python_version
            )
        )
    zip_file = response.body
    # Write to cache for next time
    with open(
        os.path.join(
            get_cache_dir(),
            "python-{0}-embed-{1}.zip".format(
                python_version_long, python_embed_byte_version
            ),
        ),
        "wb",
    ) as f:
        f.write(zip_file)
    IoLoop().current().spawn_callback(IoLoop().current().stop)


@timer()
def add_python_resources(timeout=10):
    global python_version
    global python_version_long
    global zip_file
    start_time = default_timer()
    while zip_file is None:
        if exiting or (default_timer() - start_time) > timeout:
            raise Exception("Timeout reached while waiting for Python to download")
        time.sleep(0.25)

    py_version = "python{0}".format("".join(python_version.split(".")))
    py_version_long = "python{0}".format("".join(python_version_long.split(".")))

    out_stream = BytesIO()
    stream = BytesIO(zip_file)
    with ZipFile(stream, "r") as zf:
        with ZipFile(out_stream, "w", compression=ZIP_DEFLATED) as wzf:
            hashes = {}
            i = 0
            # There will be only 3 files written - the minimal required files below
            # num_files = chr(len(zf.namelist())).encode("utf8")
            write(PY_RESOURCE_COUNT_LOCATION, chr(3).encode("utf8"))
            for py_file in zf.namelist():
                with zf.open(py_file) as ef:
                    file_data = ef.read()
                    # Minimal installation of python requires only pythonxx.dll and .zip - everything
                    #  else can be unzipped later - adding _ctypes to allow for showing popup
                    if py_file in [
                        "{0}.dll".format(py_version),
                        "{0}.zip".format(py_version),
                        "_ctypes.pyd",
                    ]:
                        write(PY_RESOURCE_FILES_START_LOCATION + i, file_data)
                        write(
                            PY_RESOURCE_NAMES_START_LOCATION + i, py_file.encode("utf8")
                        )
                        i = i + 1
                    else:
                        wzf.writestr(py_file, file_data)
                        hashes[py_file] = hashlib.sha256(file_data).hexdigest()

    py_zip_file = "{0}_{1}.zip".format(py_version_long, "64" if is_64bits else "32")
    write(PY_RESOURCE_ZIP_NAME_LOCATION, py_zip_file.encode("utf8"))
    write(PY_RESOURCE_ZIP_LOCATION, out_stream.getvalue())

    zip_hash = simplejson.dumps(hashes).encode("utf8")
    py_hash_file = "{0}_{1}hash.json".format(
        py_version_long, "64" if is_64bits else "32"
    )
    write(PY_RESOURCE_HASH_NAME_LOCATION, py_hash_file.encode("utf8"))
    write(PY_RESOURCE_HASH_LOCATION, zip_hash)


def add_to_zip(pths):
    stream = BytesIO()

    def _add_to_zip(zf, path, zippath):
        # Derived from functionality in main() of python base zipfile library
        if os.path.isfile(path):
            if path.endswith("-embed-win32.zip") or path.endswith("-embed-amd64.zip"):
                return
            if zippath is None:
                zippath = os.path.basename(path)
            zf.write(path, zippath)
        elif os.path.isdir(path):
            for nm in os.listdir(path):
                if nm == "__pycache__":
                    continue
                _add_to_zip(zf, os.path.join(path, nm), os.path.join(zippath, nm))

    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as zp:
        for mod, pth in pths:
            _add_to_zip(zp, pth, mod)

    return stream


@timer()
def add_zip_dependencies(extra_requirements=None):
    # Gather the dependency folders and zip those together to save as a resource
    if extra_requirements is None:
        extra_requirements = []
    extra_requirements.extend(["stationexec"])
    _paths_to_save = config.get_reqs(extra_requirements)
    paths_to_save = []
    for pkg, path, _version in _paths_to_save:
        paths_to_save.append((pkg, path))

    stream = add_to_zip(paths_to_save)

    write(LIB_NAME_LOCATION, b"lib.zip")
    write(LIB_FILE_LOCATION, stream.getvalue())


@timer()
def add_zip_source(station):
    extra_dependencies = []
    tool_manifest_data = config.load_config(config.get_all_paths()["tool_manifest"])
    paths_to_save = [
        (os.path.join("stations", station), config.get_all_paths()["station"])
    ]
    # Get station specified dependencies
    station_obj = config.remote_path_import(
        os.path.join(config.get_all_paths()["station"], "station.py")
    )
    extra_dependencies.extend(getattr(station_obj, "dependencies", []))
    for tool in tool_manifest_data:
        if tool["tool_type"] in ["station_storage", "config_tool"]:
            # TODO Ignore internal tools - update if new internal tools created
            continue
        paths_to_save.append(
            (os.path.join("tools", tool["tool_type"]), get_tool_path(tool["tool_type"]))
        )
        try:
            # Get tool specified dependencies
            tool = load_tool_object(tool["tool_type"], "external")
            extra_dependencies.extend(getattr(tool, "dependencies", []))
        except ToolNotFound:
            # Assume for now the tool is installed as a package and its dependencies can be queried
            extra_dependencies.append(tool["tool_type"])

    paths_to_save.append(("config", config.get_all_paths()["config_folder"]))
    stream = add_to_zip(paths_to_save)

    write(PROGRAM_NAME_LOCATION, b"src.zip")
    write(PROGRAM_FILE_LOCATION, stream.getvalue())

    return extra_dependencies


@timer()
def pack_resources(res_exe, target_exe, files):
    res_packer_args = [res_exe, "debug" if debug else "standard", target_exe]
    res_packer_args += files
    subprocess.call(args=res_packer_args)
    shutil.rmtree(temp_folder, ignore_errors=True)


def main(station, _debug=False, force_32=False):
    global debug
    global exiting
    global is_64bits
    global python_embed_byte_version
    global temp_folder

    if force_32:
        is_64bits = False
        python_embed_byte_version = "win32"

    config.set_station_identity(station)
    if not os.path.exists(config.get_all_paths()["station"]):
        print("Station '{0}' does not exist - no exe created".format(station))
        return
    print("Station Builder - creating executable for '{0}'".format(station))

    debug = _debug

    # Enable/Disable individual additions for testing
    do_update_version_string = True
    do_update_shim_file = True
    do_update_dependencies = True
    do_update_source = True
    do_update_python = True

    if not debug:
        dl = Thread(target=progress_spinner)
        dl.start()

    _start = default_timer()

    current_dir = os.path.dirname(os.path.abspath(__file__))
    if debug:
        if is_64bits:
            src_exe = os.path.join(current_dir, "launcher64.exe")
        else:
            src_exe = os.path.join(current_dir, "launcher32.exe")
    else:
        if is_64bits:
            src_exe = os.path.join(current_dir, "launcherw64.exe")
        else:
            src_exe = os.path.join(current_dir, "launcherw32.exe")

    if is_64bits:
        res_packer_exe = "resource_updater64.exe"
    else:
        res_packer_exe = "resource_updater32.exe"
    res_packer_exe = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), res_packer_exe
    )

    station_dist_folder = os.path.join(
        os.path.dirname(config.get_all_paths()["station"]), "dist"
    )
    os.makedirs(station_dist_folder, exist_ok=True)
    exe_path = os.path.join(
        station_dist_folder,
        "{0}{1}{2}.exe".format(
            station, "_d" if debug else "", "" if is_64bits else "32"
        ),
    )

    temp_folder = os.path.join(station_dist_folder, "temp")
    if os.path.exists(temp_folder):
        shutil.rmtree(temp_folder, ignore_errors=True)
    os.makedirs(temp_folder, exist_ok=True)

    dist_objects = os.listdir(station_dist_folder)
    for d in dist_objects:
        # Remove temporary files from previous failed attempts
        if d.lower().endswith(".tmp"):
            os.remove(os.path.join(station_dist_folder, d))

    if (
        do_update_version_string
        and do_update_shim_file
        and do_update_dependencies
        and do_update_source
        and do_update_python
    ):
        if os.path.exists(exe_path):
            os.remove(exe_path)
        with open(exe_path, "wb") as fw:
            with open(src_exe, "rb") as fr:
                fw.write(fr.read())

    if do_update_python:
        dl = Thread(target=download_embedded_python)
        dl.start()

    extra_dependencies = []

    # TODO Add options to shim.py if desired to load source files to a particular path or to
    #  delete source after every run or something like that

    try:
        # Add the python shim main file to be launched first
        if do_update_shim_file:
            add_shim_file()
        # Gather the station and tools
        if do_update_source:
            extra_dependencies = add_zip_source(station)
        # Add dependencies as a zip
        if do_update_dependencies:
            add_zip_dependencies(extra_dependencies)
        # Add the python executable and related files
        if do_update_python:
            add_python_resources()
        # Add version string
        if do_update_version_string:
            add_python_version_string()

        pack_resources(res_packer_exe, exe_path, target_files)
    except Exception as e:
        exiting = True
        print("Error while creating executable: {0}".format(e))
        if not debug:
            os.remove(exe_path)

        dist_objects = os.listdir(station_dist_folder)
        for d in dist_objects:
            # Remove temporary files from failed attempts
            if d.lower().endswith(".tmp"):
                os.remove(os.path.join(station_dist_folder, d))
        raise e

    exiting = True

    _end = default_timer()
    if debug:
        print("-- Total: {0}s".format(_end - _start))

    time.sleep(0.3)
    print(
        "\n'{0}' created in '{1}'".format(
            os.path.basename(exe_path), os.path.dirname(exe_path)
        )
    )


if __name__ == "__main__":
    main("hello_prpl")
