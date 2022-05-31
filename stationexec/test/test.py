# Copyright 2004-present Facebook. All Rights Reserved.

import sys

# noinspection PyPackageRequirements,PyUnresolvedReferences
from nose.tools import assert_equals as _assert

from stationexec.main import Main, parse_args
from stationexec.utilities.ioloop_ref import IoLoop


def test_start():
    sys.argv = ["", "-f", "single_eyecup_example_1.json", "-p", "8100"]
    main = Main(parse_args())
    io_loop = IoLoop().current()
    io_loop.call_later(4, io_loop.stop)
    main.start()
    _assert(('b' * 2), 'bb')
