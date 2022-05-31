# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

# Derived from:
#   https://www.python.org/download/releases/2.2/descrintro/#__new__


class Singleton(object):
    def __new__(cls, *args, **kwargs):
        it = cls.__dict__.get("__it__")
        if it is None:
            cls.__it__ = it = object.__new__(cls)
        return it

    def init(self, *args, **kwargs):
        """ Override this as needed. """
        pass
