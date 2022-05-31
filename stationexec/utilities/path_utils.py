# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import os
import shutil

import pkg_resources

_in_zip = None


def installed_in_zip():
    global _in_zip
    if _in_zip is None:
        _in_zip = ".zip" in os.path.abspath(__file__)
    return _in_zip


def _path_in_zip(pth):
    return ".zip" in pth


# ---------------------------------------------------------------------------


def is_dir(pth):
    if not _path_in_zip(pth) or not installed_in_zip():
        return os.path.isdir(pth)
    return pkg_resources.resource_isdir("stationexec", pth)


def is_file(pth):
    if not _path_in_zip(pth) or not installed_in_zip():
        return os.path.isfile(pth)
    return not is_dir(pth)


def exists(pth):
    if not _path_in_zip(pth) or not installed_in_zip():
        return os.path.exists(pth)
    return pkg_resources.resource_exists("stationexec", pth)


def list_dir(pth):
    if not _path_in_zip(pth) or not installed_in_zip():
        return os.listdir(pth)
    if not is_dir(pth):
        raise NotADirectoryError("The directory name is invalid: '{0}'".format(pth))
    return pkg_resources.resource_listdir("stationexec", pth)


def get_file_content(pth):
    if not _path_in_zip(pth) or not installed_in_zip():
        with open(pth, "rb") as f:
            return f.read()
    return pkg_resources.resource_string("stationexec", pth)


def copy_file(pth, target):
    if not _path_in_zip(pth) or not installed_in_zip():
        shutil.copy(pth, target)
        return
    with open(target, "wb") as f:
        f.write(pkg_resources.resource_string("stationexec", pth))


def copy_tree(pth, target):
    if not _path_in_zip(pth) or not installed_in_zip():
        shutil.copytree(pth, target)
        return

    pth = pth.rsplit("stationexec", 1)[1]
    pth = "/".join(pth.split(os.sep))
    if pth.startswith("/"):
        pth = pth.split("/", 1)[1]

    def _extract(_pth, _target):
        if pkg_resources.resource_isdir("stationexec", _pth):
            for nm in pkg_resources.resource_listdir("stationexec", _pth):
                _extract(_pth + "/" + nm, os.path.join(_target, nm))
        else:
            os.makedirs(os.path.dirname(_target), exist_ok=True)
            with open(_target, "wb") as f:
                f.write(pkg_resources.resource_string("stationexec", _pth))

    _extract(pth, target)
