# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import tornado.ioloop
from stationexec.utilities.singleton import Singleton


class IoLoop(Singleton):
    """
    Singleton class for ioloop reference -  required for asyncio based versions of tornado
    (all versions starting at v5) to reference the same ioloop in threads

    http://www.tornadoweb.org/en/stable/ioloop.html#tornado.ioloop.IOLoop.instance
    """

    ioloop_instance = None

    def init(self):
        self.ioloop_instance = tornado.ioloop.IOLoop.current()

    def current(self):
        return self.ioloop_instance
