# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
Database object definitions

All times must be stored in UTC format
"""
import simplejson
from sqlalchemy import Column, DateTime, Integer, LargeBinary, Numeric, SmallInteger, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import deferred
from sqlalchemy.types import TypeDecorator

from stationexec.utilities.time import get_utc_now


Base = declarative_base()


class JSONEncoded(TypeDecorator):
    """Store value as JSON string -
    https://docs.sqlalchemy.org/en/13/core/custom_types.html#marshal-json-strings"""
    impl = LargeBinary(length=(2 ** 32) - 1)

    def process_bind_param(self, value, dialect):
        # Process value on the way to storage
        # In what seems to be undocumented behavior (even going against the link above),
        # the 'value' shows up already formatted as a JSON string no matter if the passed in
        # value is a string, dict, or list. Tested with simple values and with dict that has
        # nested lists and dicts and it performed fine.
        if isinstance(value, dict):
            val = simplejson.dumps(value)
        elif isinstance(value, str) or value is None:
            val = value
        else:
            val = value
        if val is None:
            val = ""
        return val.encode("utf8")

    def process_result_value(self, value, dialect):
        # Process value on retrieval
        val = value.decode("utf8")
        if val is None or val == "":
            return None
        else:
            return simplejson.loads(val)


class Station(Base):
    __tablename__ = "stations"
    uuid = Column(String(32), primary_key=True, unique=True, nullable=False)
    variant = Column(String(64), nullable=False, index=True)
    instance = Column(String(64), nullable=False, index=True)
    macaddress = Column(String(64))
    hostname = Column(String(64))
    location = Column(String(32))
    lineid = Column(String(32))
    preferences = Column(JSONEncoded, default=None)
    info = Column(JSONEncoded, default=None)
    created = Column(DateTime, default=get_utc_now)
    updated = Column(DateTime, default=get_utc_now)


class SequenceStart(Base):
    __tablename__ = "sequence_starts"
    uuid = Column(String(32), primary_key=True, unique=True, nullable=False)
    station = Column(String(32), nullable=False)
    info = Column(JSONEncoded, default=None)
    created = Column(DateTime, default=get_utc_now, index=True)
    runtimedata = Column(JSONEncoded, default=None)
    version = Column(Text)


class SequenceEnd(Base):
    __tablename__ = "sequence_ends"
    uuid = Column(String(32), primary_key=True, unique=True, nullable=False)
    passing = Column(SmallInteger, nullable=False, default=0, index=True)
    duration = Column(Integer, nullable=False)
    info = Column(JSONEncoded, default=None)
    created = Column(DateTime, default=get_utc_now, index=True)


class OperationStart(Base):
    __tablename__ = "operation_starts"
    uuid = Column(String(32), primary_key=True, unique=True, nullable=False)
    opid = Column(String(255), default=None)
    sequence = Column(String(32), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(255), default=None)
    priority = Column(Integer, nullable=False)
    info = Column(JSONEncoded, default=None)
    created = Column(DateTime, default=get_utc_now, index=True)


class OperationEnd(Base):
    __tablename__ = "operation_ends"
    uuid = Column(String(32), primary_key=True, unique=True, nullable=False)
    passing = Column(SmallInteger, nullable=False, default=0, index=True)
    duration = Column(Integer, nullable=False)
    waittime = Column(Integer, default=0)
    exitcode = Column(SmallInteger, nullable=False)
    info = Column(JSONEncoded, default=None)
    created = Column(DateTime, default=get_utc_now, index=True)


class Result(Base):
    __tablename__ = "results"
    uuid = Column(String(32), primary_key=True, unique=True, nullable=False)
    operation = Column(String(32), nullable=False)
    identifier = Column(String(64), default=None, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(255), default=None)
    value = Column(Numeric, nullable=False)
    passing = Column(SmallInteger, nullable=False, default=0, index=True)
    operator = Column(String(32), nullable=False)
    # The value itself is considered Operand 1; result < operand2 or result inrange(op2, op3)
    operand2 = Column(Numeric, nullable=False)
    operand3 = Column(Numeric)
    info = Column(JSONEncoded, default=None)
    created = Column(DateTime, default=get_utc_now)


class DataStorage(Base):
    __tablename__ = "data"
    uuid = Column(String(32), primary_key=True, unique=True, nullable=False)
    operation = Column(String(32), nullable=False)
    identifier = Column(String(64), default=None, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(255), default=None)
    # https://stackoverflow.com/questions/43791725/sqlalchemy-how-to-make-a-longblob-column-in-mysql
    value = deferred(Column(LargeBinary(length=(2 ** 32) - 1), nullable=False))
    mimetype = Column(String(255), nullable=False)
    size = Column(Integer, nullable=False)
    info = Column(JSONEncoded, default=None)
    created = Column(DateTime, default=get_utc_now)


class Logging(Base):
    __tablename__ = "logging"
    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    stream = Column(String(16), nullable=False)
    message = Column(Text, nullable=False)
    created = Column(DateTime, default=get_utc_now, index=True)

    def __repr__(self):
        return "Log('{0}', '{1}')".format(self.stream, self.message)


class Maintenance(Base):
    __tablename__ = "maintenance"
    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    message = Column(Text, nullable=False)
    created = Column(DateTime, default=get_utc_now, index=True)
