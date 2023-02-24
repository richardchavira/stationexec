# Copyright 2004-present Facebook. All Rights Reserved.

# coding=utf-8
from setuptools import setup

version = {}
# Read in version from stationexec/version.py
with open("stationexec/version.py") as v:
    exec(v.read(), version)


setup(
    name="stationexec",
    version=version["version"],
    packages=["stationexec", "stationexec.cli",
              "stationexec.logger", "stationexec.sequencer", "stationexec.station",
              "stationexec.test", "stationexec.toolbox", "stationexec.utilities",
              "stationexec.web"],
    include_package_data=True,
    author="Meta Hardware Engineering",
    license="TBD",
    url="https://www.meta.com",
    description=("Station Exec is a light-weight, flexible software framework for"
                 "sequencing tasks and interacting with external data sources."),
    long_description=open("README.rst").read(),
    install_requires=[
        "addict",
        "arrow == 0.17.0",
        "colorama",
        "pymysql",
        "setuptools",
        "simplejson",
        "sqlalchemy",
        "tornado == 5.1.1",
        "wheel"
    ],
    entry_points={
        "console_scripts": [
            "se-hello=stationexec.cli.cli_tools:cli_hello",
            "se-setup=stationexec.cli.cli_tools:cli_setup",
            "se-start=stationexec.cli.cli_tools:cli_start",
            "se-launch=stationexec.cli.cli_tools:cli_start",
            "se-station=stationexec.cli.cli_tools:cli_station",
            "se-tool=stationexec.cli.cli_tools:cli_tool",
            "se-which=stationexec.cli.cli_tools:cli_which",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11"
    ]
)
