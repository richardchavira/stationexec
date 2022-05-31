# Copyright 2004-present Facebook. All Rights Reserved.


class ClassProperty(property):
    """
    Support definition of class-level properties in static classes.

    see https://stackoverflow.com/a/1383402/1663987
    """

    # noinspection PyMethodOverriding,PyUnresolvedReferences
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()
