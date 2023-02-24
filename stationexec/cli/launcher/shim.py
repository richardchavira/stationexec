# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import argparse
import ctypes
import hashlib
import inspect
import json
import os
import shutil
import sys
import time
import traceback
from ctypes.wintypes import HWND, UINT, WPARAM, LPARAM, LONG
from threading import Thread
from timeit import default_timer
from zipfile import ZipFile

dialog_handle = None


def hash_object(pth):
    def _hash_object(path, active_hash):
        if os.path.isfile(path):
            with open(path, "rb") as h_file:
                active_hash.update(h_file.read())
        elif os.path.isdir(path):
            for nm in os.listdir(path):
                if nm == "__pycache__":
                    continue
                _hash_object(os.path.join(path, nm), active_hash)

    zip_hash = hashlib.sha256()
    _hash_object(pth, zip_hash)
    return zip_hash.hexdigest()


def compare_and_extract(target, debug=False, ignore=None):
    extract_all = False
    if not os.path.exists(target):
        extract_all = True
        os.mkdir(target)

    if ignore is None:
        ignore = []
    # Compare hashes of objects and extract only files that have changed
    to_extract = []
    with open("{0}hash.json".format(target), "r") as f1:
        new_hashes = json.load(f1)

    old = set(os.listdir(target))
    new = set(new_hashes.keys())
    # Remove files that are in the old file set that don't exist in the new set
    for rm_item in list(old - new):
        if rm_item in ignore:
            continue
        if os.path.isdir(os.path.join(target, rm_item)):
            shutil.rmtree(os.path.join(target, rm_item))
        else:
            os.remove(os.path.join(target, rm_item))

    for lib, lib_hash in new_hashes.items():
        if lib_hash != hash_object(os.path.join(target, lib)):
            to_extract.append(lib)

    # Unpack dependencies
    extract(target, target, to_extract, extract_all)

    if not debug:
        os.remove("{0}.zip".format(target))
        os.remove("{0}hash.json".format(target))


def extract(target, destination, to_extract=None, extract_all=False):
    if to_extract is None:
        to_extract = []
    with ZipFile("{0}.zip".format(target)) as zf:
        if extract_all:
            zf.extractall(destination)
        else:
            members = zf.namelist()
            for mod in to_extract:
                shutil.rmtree(os.path.join(target, mod), ignore_errors=True)
                for fl in members:
                    if fl.startswith(mod):
                        zf.extract(fl, destination)


def launch_window():
    # Solutions to several problems herein inspired by those in Venster
    # https://github.com/toymachine/venster
    class RECT(ctypes.Structure):
        _fields_ = [("left", LONG), ("top", LONG), ("right", LONG), ("bottom", LONG)]

    def dlg(hwnd, _uMsg, _wParam, _lParam):
        global dialog_handle
        if dialog_handle is None:
            dialog_handle = hwnd
        if _uMsg == 0x110:
            hnd = ctypes.windll.user32.GetDesktopWindow()
            rc_screen = RECT()
            rc_dialog = RECT()
            ctypes.windll.user32.GetWindowRect(hnd, ctypes.byref(rc_screen))
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rc_dialog))
            left = (rc_screen.right / 2) - (rc_dialog.right / 2)
            top = (rc_screen.bottom / 2) - (rc_dialog.bottom / 2)
            ctypes.windll.user32.SetWindowPos(hwnd, 0, int(left), int(top), 0, 0, 1)
        return False

    def dialog():
        ctypes.windll.user32.DialogBoxParamW(0, 101, 0, DialogProc(dlg), 0)

    DialogProc = ctypes.WINFUNCTYPE(ctypes.c_int, HWND, UINT, WPARAM, LPARAM)
    alert = Thread(target=dialog)
    alert.start()


def destroy_window(wait=5):
    global dialog_handle
    start = default_timer()
    while dialog_handle is None:
        time.sleep(0.1)
        if (default_timer() - start) > wait:
            raise Exception("Could not destroy window in time")
    res = ctypes.windll.user32.EndDialog(dialog_handle, 0)
    if res == 0:
        raise ctypes.WinError()
    dialog_handle = None


def find_station_to_launch():
    stations = []
    station_dir = os.path.join(os.getcwd(), "work_dir", "stationexec", "stations")
    for st in os.listdir(station_dir):
        if st.startswith("__") or st == "hello_prpl":
            continue
        stations.append(st)
    if len(stations) < 1:
        return "hello_prpl"
    else:
        return stations[0]


def main():
    try:
        parser = argparse.ArgumentParser(description="StationExec Setup")
        parser.add_argument(
            "--debug", help="Show debug log info", action="store_true", required=False
        )
        # parser.add_argument("-i", help="Interactive installation - load into REPL", action="store_true",
        #                     required=False)
        args, _ = parser.parse_known_args(sys.argv[1:])

        debug = args.debug

        os.chdir(os.path.dirname(sys.argv[0]))

        is_64bits = sys.maxsize > 2 ** 32
        version = "python{0}{1}".format(sys.version_info.major, sys.version_info.minor)
        version_long = "python{0}{1}{2}_{3}".format(
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro,
            "64" if is_64bits else "32",
        )

        # Add environment variable to get path to the python executable (helpful for subprocess calls)
        os.environ["__SE_EXE_PATH__"] = os.path.join(
            os.getcwd(), version_long, "python.exe"
        )

        # if args.i:
        #     import code
        #     code.interact(local=locals())
        #     sys.exit()

        _start = default_timer()

        # ---------------------------------------------

        launch_window()

        _s = default_timer()
        ignore = ["{0}.dll".format(version), "{0}.zip".format(version), "_ctypes.pyd"]
        compare_and_extract(version_long, debug, ignore=ignore)
        _e = default_timer()
        if debug:
            print("Python Extract: {0}s".format(_e - _s))

        # ------------------------

        from stationexec.cli.cli_tools import cli_setup, cli_start

        # Run stationexec cli se_setup if main path doesn't exist
        # If it does exist, re-install everything except for Log and Data folders
        cli_setup(
            force=False,
            silent=True,
            refresh_install=True,
            alt=os.path.join(os.getcwd(), "work_dir", "stationexec"),
        )

        # Copy station and tools to proper stationexec folder
        _s = default_timer()
        extract(
            "src",
            os.path.join("work_dir", "stationexec"),
            to_extract=None,
            extract_all=True,
        )
        # Always remove src.zip for protection
        os.remove("src.zip")
        _e = default_timer()
        if debug:
            print("Src Extract: {0}s".format(_e - _s))

        _end = default_timer()
        if debug:
            print("Setup took {0}s".format(_end - _start))

        destroy_window()

        # ---------------------------------------------

        # Add environment variable to detect when in package
        os.environ["__SE_EXE__"] = "True"

        # Launch a monitoring process that will refresh the installation after the program exits
        from multiprocessing import Process, freeze_support, set_executable

        freeze_support()
        py_exe_path = os.path.abspath(os.path.join(version_long, "pythonw.exe"))
        set_executable(py_exe_path)
        p = Process(target=process_monitor)
        p.start()
        # TODO May need to catch signals in here to shutdown this external process - it can hang if killed
        #  at an inconvenient time (early in the launch process it seems)

        try:
            station = find_station_to_launch()
            print(station)
            sys.argv = ["", station]
            cli_start()
        except Exception as e:
            print("Program run exception")
            print(e)
            print(get_stack_trace())
            with open("error.txt", "a") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
                f.write("Program run exception")
                f.write(str(e))
                f.write(get_stack_trace())

    except Exception as e:
        destroy_window()
        print(e)
        print(get_stack_trace())
        with open("error.txt", "a") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
            f.write(str(e))
            f.write(get_stack_trace())


def get_stack_trace():
    atype, value, tb = sys.exc_info()
    name = atype.__name__
    stack_trace = "Exception Occurred\n"
    stack_trace += "  {0}: {1}\n".format(name, value)
    for item in traceback.format_tb(tb, 7):
        stack_trace += "    {0}\n".format(item.rstrip('\r\n'))
    return stack_trace


def _get_class_from_frame(fr):
    args, _, _, value_dict = inspect.getargvalues(fr)
    # we check the first parameter for the frame function is named 'self'
    if len(args) and args[0] == 'self':
        # in that case, 'self' will be referenced in value_dict
        the_class = fr.f_locals["self"].__class__.__name__
        the_method = fr.f_code.co_name
        return "{}.{}()".format(str(the_class), the_method)
    return None


def process_monitor():
    from stationexec.cli.cli_tools import cli_setup
    from tornado.httpclient import HTTPRequest, HTTPClient, HTTPError

    request = HTTPRequest(
        url="http://localhost:8888/isalive",
        method="GET",
        follow_redirects=False,
        request_timeout=1,
    )
    client = HTTPClient()
    com_errors = 0
    max_com_errors = 3
    time.sleep(5)
    while True:
        try:
            # Check on process somehow
            client.fetch(request)
            com_errors = 0
        except (HTTPError, RuntimeError, ConnectionResetError):
            com_errors += 1
        if com_errors >= max_com_errors:
            cli_setup(
                force=False,
                silent=True,
                refresh_install=True,
                alt=os.path.join(os.getcwd(), "work_dir", "stationexec"),
            )
            return
        time.sleep(1)


if __name__ == "__main__":
    main()
