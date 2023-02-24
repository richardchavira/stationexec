# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import types

from stationexec.sequencer.sequence import Sequence
from stationexec.utilities import config


def from_file(
    config_path,
    code_path,
    tool_functions,
    system_configs,
    n_up=1,
    avg_operation_runtimes=None,
    runtimedata=None,
):
    with open(code_path) as f:
        op_file = f.read()
    return from_text(
        config.load_config(config_path),
        op_file,
        tool_functions,
        system_configs,
        n_up,
        avg_operation_runtimes,
        runtimedata,
    )


def from_text(
    config_text,
    code_text,
    tool_functions,
    system_configs,
    n_up=1,
    avg_operation_runtimes=None,
    runtimedata=None,
):
    sequence_module = types.ModuleType("operations")
    exec(code_text, sequence_module.__dict__)
    return _factory(
        config_text,
        sequence_module,
        tool_functions,
        system_configs,
        n_up,
        avg_operation_runtimes,
        runtimedata,
    )


def _factory(
    sequence_config,
    sequence_module,
    tool_functions,
    system_configs,
    n_up=1,
    avg_operation_runtimes=None,
    runtimedata=None,
):
    sequence = Sequence(
        sequence_config,
        tool_functions,
        system_configs,
        avg_operation_runtimes=avg_operation_runtimes,
        runtimedata=runtimedata,
        n_up=n_up,
    )
    sequence.initialize(sequence_module)
    return sequence
