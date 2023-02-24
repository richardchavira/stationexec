# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import os
from contextlib import contextmanager
from datetime import timedelta

import simplejson
from sqlalchemy import create_engine, desc, func, inspect
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from tornado.escape import url_escape

from stationexec.logger import log
from stationexec.station.events import RetrievalEvents, StorageEvents
from stationexec.toolbox.tool import Tool
from stationexec.utilities import config
from stationexec.utilities.time import get_utc_now, local_to_utc, utc_to_local, to_datetime
from stationexec.utilities import uuidstr
from stationexec.web.handlers import ExecutiveHandler

from station_storage.tables import (
    Base,
    Logging,
    Maintenance,
    OperationStart,
    OperationEnd,
    ErrorCode,
    Result,
    DataStorage,
    SequenceStart,
    SequenceEnd,
    Station,
    User,
)

# TODO Allow db password from command line? How to let it not be hardcoded somewhere?
#  push hard for certs?
version = "1.3"
dependencies = []
default_configurations = {
    "db_config": {
        "host": None,
        "database": None,
        "user": None,
        "password": None,
        "ca": None,
        "cert": None,
        "key": None,
    },
    "active_modules": None,
    "log_level": 3,
}


class UniqueViolationDbException(Exception):
    # Tried to insert duplicate data in a unique column
    pass


class StationStorage(Tool):
    """ Setup tool with configuration arguments """

    def __init__(
        self,
        db_config,
        active_modules=None,
        log_level=3,
        sqlite_filename="storage.sqlite",
        custom=False,
        db_base=None,
        **kwargs,
    ):
        super(StationStorage, self).__init__(**kwargs)
        known_modules = [
            "logging",
            "operation_starts",
            "operation_ends",
            "stations",
            "results",
            "data",
            "error_codes",
            "sequence_starts",
            "sequence_ends",
            "users"
            # "custom", "maintenance"
        ]

        self._log_level = log_level

        if db_base is None:
            db_base = Base
        self.db_base = db_base

        if active_modules is None:
            active_modules = known_modules
        else:
            if not custom:
                unknown_db_modules = [
                    module for module in active_modules if module not in known_modules
                ]
                if len(unknown_db_modules) > 0:
                    raise Exception(
                        "Unknown database module(s) configured: {0}".format(
                            ", ".join(unknown_db_modules)
                        )
                    )

        self._active_modules = active_modules

        if db_config.get("user") and db_config.get("host"):
            # Connect to remote MySQL Host
            self._engine = create_engine(
                "mysql+pymysql://{0}:{1}@{2}:{3}/{4}".format(
                    db_config.get("user"),
                    url_escape(db_config.get("password")),
                    db_config.get("host"),
                    db_config.get("port", 3306),
                    db_config.get("database"),
                ),
                echo=False,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 3},
            )
        else:
            # Create local SQLite db
            sql_file = os.path.join(
                config.get_all_paths()["data_folder"], sqlite_filename
            )
            # echo = self.debug > 10
            self._engine = create_engine(
                "sqlite:///{0}".format(sql_file), echo=False, pool_pre_ping=True
            )

        self._session = sessionmaker(bind=self._engine)
        self._is_initialized = False

        if custom:
            # This is a custom override of storage class - no need to register for events
            return

        # Register for Events

        reg = self.listen_for_event

        if "custom_events" in self._active_modules:
            # TODO Define how custom events will work
            reg(StorageEvents.ON_CUSTOM_STORAGE, None)
            reg(RetrievalEvents.GET_CUSTOM_DATA, None)

        if "sequence_starts" in self._active_modules:
            reg(StorageEvents.ON_SEQUENCE_START, self.on_sequence_start)
        if "sequence_ends" in self._active_modules:
            reg(StorageEvents.ON_SEQUENCE_END, self.on_sequence_end)
        
        if "operation_starts" in self._active_modules:
            reg(StorageEvents.ON_OPERATION_START, self.on_operation_start)
        if "operation_ends" in self._active_modules:
            reg(StorageEvents.ON_OPERATION_END, self.on_operation_end)
        if (
            "operation_starts" in self._active_modules
            and "operation_ends" in self._active_modules
        ):
            reg(
                RetrievalEvents.GET_OPERATION_AVERAGE_DURATION,
                self.get_operation_average_duration,
            )

        if "results" in self._active_modules:
            reg(StorageEvents.ON_RESULT_STORE, self.on_result_store)
        if "data" in self._active_modules:
            reg(StorageEvents.ON_DATA_STORE, self.on_data_store)
        if "error_codes" in self._active_modules:
            reg(StorageEvents.ON_ERROR_CODE, self.on_error_code)


        if "stations" in self._active_modules:
            reg(StorageEvents.ON_REGISTER_STATION_LOCAL, self.on_register_new_station)
            # reg(StorageEvents.ON_UPDATE_STATION, self.on_update_station)
            reg(RetrievalEvents.GET_STATION_DATA_LOCAL, self.get_station_data)

        if "maintenance" in self._active_modules:
            # TODO Expand maintenance events to a usable state
            reg(StorageEvents.ON_MAINTENANCE_EVENT, self.on_maintenance_data)
            reg(RetrievalEvents.GET_MAINTENANCE_DATA, self.get_maintenance_data)

        # Helper Registration events
        if (
            "sequence_starts" in self._active_modules
            and "sequence_ends" in self._active_modules
        ):
            reg(RetrievalEvents.GET_SEQUENCES, self.get_sequences)

            if (
                "operation_starts" in self._active_modules
                and "operation_ends" in self._active_modules
            ):
                reg(
                    RetrievalEvents.GET_SEQUENCE_OPERATIONS,
                    self.get_sequence_operations,
                )

                if "results" in self._active_modules:
                    reg(RetrievalEvents.GET_SEQUENCE_RESULTS, self.get_sequence_results)

                if "data" in self._active_modules:
                    reg(RetrievalEvents.GET_SEQUENCE_DATA, self.get_sequence_data)

        # Register Log events last so that the event registrations do not show up in the log
        if "logging" in self._active_modules:
            reg(RetrievalEvents.GET_LOG_DATA, self.get_log_data)
            reg(StorageEvents.ON_LOG_DATA, self.on_log_data)

    def initialize(self):
        """ Prepare tool for operation """
        try:
            # TODO What happens here if the tables are different than what exists already?
            db_tables = [
                self.db_base.metadata.tables[table] for table in self._active_modules
            ]
            self.db_base.metadata.create_all(bind=self._engine, tables=db_tables)
        except OperationalError as e:
            if "timed out" in str(e):
                log.error("Database connection timeout: {0}".format(str(e)))
                return False
            else:
                # Something is wrong and we cannot fix it
                raise
        else:
            self._is_initialized = True

    def verify_status(self):
        """ Check that tool is online; attempt to repair if not. Called every 5 seconds. """
        if self.is_online:
            try:
                # Run a check to make sure all is working well
                insp = inspect(self._engine)
                not_exists = [
                    table
                    for table in self._active_modules
                    if insp.has_table(table) is False
                ]
                if len(not_exists) > 0:
                    self.set_offline()
            except Exception as e:
                log.exception("Exception while checking database status", e)
                self.set_offline()

        if not self.is_online:
            return self.initialize()

    def shutdown(self):
        """ Cleanup tool for program shutdown """
        pass

    def on_ui_command(self, command, **kwargs):
        """ Command received from UI """
        if command == "cleanup":
            self.cleanup()
        if command == "delete":
            tbl = kwargs.get("table")
            self.clear_table(tbl)

    def cleanup(self):
        self._engine.execute("vacuum;")

    def clear_table(self, table):
        if table == "logging":
            self._engine.execute(f"DELETE FROM logging;")

    def read_logs(self):
        results = self._engine.execute(f"SELECT * FROM logging order by created desc;")
        data = []
        for row in results.fetchall():
            row_data = {}
            for key in row._keymap:
                row_data[key] = row[key]
            data.append(row_data)
        return data

    def add_user(self, name, pwd_hash, salt, user_info):
        with self.session() as s:
            info = {
                "name": name,
                "password_hash": pwd_hash,
                "password_salt": salt,
                "user_info": user_info,
            }
            s.add(User(**info))

    def get_info(self):
        tables = self.get_table_info()
        data_path = config.get_all_paths()["data_folder"]
        database_path = os.path.join(data_path, "storage.sqlite")
        file_size = os.path.getsize(database_path)
        file_info = {"file_location": database_path, "file_size": file_size}

        info = {"tables": tables, "file_info": file_info}
        return info

    def get_table_info(self):
        results = self._engine.execute(
            "SELECT name from sqlite_master WHERE type='table' and name NOT LIKE 'sqlite_%';"
        )
        table_list = (row[0] for row in results.fetchall())
        tables = {}
        for tbl in table_list:
            result = self._engine.execute(f"SELECT count(*) as count FROM {tbl};")
            tables[tbl] = result.fetchone()[0]

        return tables

    def get_endpoints(self):
        endpoints = [
            (f"/tool/{self.tool_id}/table_info", InfoHandler, {"tool": self}),
            (f"/tool/{self.tool_id}/table_data", DataHandler, {"tool": self}),
        ]
        return endpoints

    @contextmanager
    def session(self):
        if not self._is_initialized:
            try:
                yield None
            except AttributeError:
                # Deliberately caused this error by yielding a None, which has no attributes,
                # to exit the context manager early, due to storage not yet being initialized
                return

        s = self._session()
        s.expire_on_commit = False
        try:
            yield s
        except Exception:
            # Exception during session - cleanup and raise exception higher
            s.rollback()
            log.error("DB session provider saw exception")
            raise
        else:
            try:
                s.commit()
            except OperationalError as e:
                # OperationalError is a catch-all for "something went wrong"
                log.error("Database operational error")
                if "no such table" in str(e):
                    # Sqlite tables are missing - maybe the file was deleted?
                    # Set offline so tables will be recreated
                    self.set_offline()
                raise
            except IntegrityError:
                log.error("Database integrity violation")
                raise
        finally:
            s.close()

    # --------------------------------------------------------------------------------------------

    def get_user_info(self, name, evt=None):
        with self.session() as s:
            query = s.query(
                User.id,
                User.name,
                User.password_hash,
                User.password_salt,
                User.user_info,
            ).filter(User.name == name)

        result = query.all()
        info = {}
        if result:
            info = {
                "id": result[0][0],
                "name": result[0][1],
                "password_hash": result[0][2],
                "password_salt": result[0][3],
                "user_info": result[0][4],
            }
        return info

    def on_sequence_start(self, data, evt=None):
        """
        Store the beginning of a sequence

        Event emitted in sequencer._execute

            seq_start = {
                "uuid": unique ID for operation
                "station": uuid of sequence the sequence is running on
                "info": optional dict of metadata
                "runtimedata": optional dict of data given to sequence at runtime
                "version": version string of the sequence
                "created": timestamp of record
            }

        "created" time usually added by caller - time the record was generated (as opposed
        to now, when the record is stored, in case there is a delay)

        :param list data: sequence starting data to store
        :param str evt: event the data came from
        :return: None
        """
        with self.session() as s:
            for seq_start in data:
                seq_data = {
                    "uuid": seq_start.get("uuid"),
                    "station": seq_start.get("station"),
                    "info": seq_start.get("info"),
                    "runtimedata": seq_start.get("runtimedata"),
                    "version": seq_start.get("version"),
                    "created": seq_start.get("created"),
                }
                s.add(SequenceStart(**seq_data))

    def on_sequence_end(self, data, evt=None):
        """
        Store the end of a sequence

        Event emitted in sequencer._execute

            seq_end = {
                "uuid": unique ID for operation (same as from on_operation_start)
                "passing": whether the sequence was considered successful
                "duration_ms": execution time of sequence (milliseconds)
                "info": optional dict of metadata
                "created": timestamp of record
            }

        "created" time usually added by caller - time the record was generated (as opposed
        to now, when the record is stored, in case there is a delay)

        :param list data: sequence ending data to store
        :param str evt: event the data came from
        :return: None
        """
        with self.session() as s:
            for seq_end in data:
                seq_data = {
                    "uuid": seq_end.get("uuid"),
                    "passing": seq_end.get("passing"),
                    "duration": seq_end.get("duration_ms"),
                    "info": seq_end.get("info"),
                    "created": seq_end.get("created"),
                }
                s.add(SequenceEnd(**seq_data))

    def on_operation_start(self, data, evt=None):
        """
        Store the beginning of an operation

        Event emitted in sequencer._run_ready_operations

            op_start = {
                "uuid": unique ID for operation
                "opid": identifying name of operation
                "sequence": uuid of sequence
                "name": user given name of the operation
                "description": string description of operation
                "priority": numeric priority of operation
                "info": optional dict of metadata
                "created": timestamp of record
            }

        "created" time usually added by caller - time the record was generated (as opposed
        to now, when the record is stored, in case there is a delay)

        :param list data: operation starting data to store
        :param str evt: event the data came from
        :return: None
        """
        with self.session() as s:
            for op_start in data:
                op_data = {
                    "uuid": op_start.get("uuid"),
                    "opid": op_start.get("opid"),
                    "name": op_start.get("name"),
                    "sequence": op_start.get("sequence"),
                    "description": op_start.get("description"),
                    "priority": op_start.get("priority"),
                    "info": op_start.get("info"),
                    "created": op_start.get("created"),
                }
                s.add(OperationStart(**op_data))

    def on_operation_end(self, data, evt=None):
        """
        Store the end of an operation

        Event emitted in sequencer._operation_done

            op_end = {
                "uuid": unique ID for operation (same as from on_operation_start)
                "passing": True if operation considered passing; False otherwise
                "duration_ms": execution time of operation (milliseconds)
                "waittime_ms": how long the operation spent waiting for tools (milliseconds)
                "exitcode": numeric status value of completion - 100 is successful
                "info": optional dict of metadata
                "created": timestamp of record
            }

        "created" time usually added by caller - time the record was generated (as opposed
        to now, when the record is stored, in case there is a delay)

        :param list data: operation ending data to store
        :param str evt: event the data came from
        :return: None
        """
        with self.session() as s:
            for op_end in data:
                op_data = {
                    "uuid": op_end.get("uuid"),
                    "passing": op_end.get("passing"),
                    "duration": op_end.get("duration_ms"),
                    "waittime": op_end.get("waittime_ms"),
                    "exitcode": op_end.get("exitcode"),
                    "info": op_end.get("info"),
                    "created": op_end.get("created")
                }
                s.add(OperationEnd(**op_data))
    
    def on_error_code(self, data, evt=None):
        """
        Save error code entry to table
        
        err_code = {
                "uuid": Unique ID for error code table entry
                "operation": unique ID for operation (same as from on_operation_start)
                "project_code": int
                "component_code": hardware that caused the error
                "error_code": type of failure or error
                "debug_message": relevant info from the error occurance,
                "timestamp": timestamp of record, datetime
            }

        "created" time usually added by caller - time the record was generated (as opposed
        to now, when the record is stored, in case there is a delay)

        :param list data: operation ending data to store
        :param str evt: event the data came from
        :return: None
        """
        with self.session() as s:
            for err_code in data:
                err_code_data = {
                    "uuid": err_code.get("uuid"),
                    "operation": err_code.get("operation"),
                    "project_code": err_code.get("project_code"),
                    "component_code": err_code.get("component_code"),
                    "error_code": err_code.get("error_code"),
                    "debug_message": err_code.get("debug_message"),
                    "timestamp": to_datetime(err_code.get("timestamp")),
                }
                s.add(ErrorCode(**err_code_data))

    def on_result_store(self, data, evt=None):
        """
        Store a sequence numeric result

        Event emitted in sequencer._operation_done

            result = {
                "uuid": unique ID for result
                "operation": uuid of the operation that stored the result
                "name": what the result is called
                "identifier": optional identifier tag to relate this result to something else
                                (like a serial number)
                "description": string description of what the result is
                "value": data itself
                "passing": is the value between the specified bounds
                "operator": how the result will be compared to the operands
                "operand2": right side of the equation for most comparisons
                "operand3": second bound for a range comparison
                "lower": lower bound of numeric result
                "upper": upper bound of numeric result
                "created": timestamp of record
            }

        "created" time usually added by caller - time the record was generated (as opposed
        to now, when the record is stored, in case there is a delay)

        :param list data: results to store
        :param str evt: event the data came from
        :return: None
        """
        with self.session() as s:
            for result in data:
                result_data = {
                    "uuid": result.get("uuid"),
                    "operation": result.get("operation"),
                    "name": result.get("name"),
                    "identifier": result.get("identifier"),
                    "description": result.get("description"),
                    "value": result.get("value"),
                    "passing": result.get("passing"),
                    # The value itself is considered Operand 1; result < operand2 or
                    # result inrange(op2, op3)
                    "operator": result.get("operator"),
                    "operand2": result.get("operand2"),
                    "operand3": result.get("operand3"),
                    "created": result.get("created"),
                }
                s.add(Result(**result_data))

    def on_data_store(self, data, evt=None):
        """
        Store non-result data

        Event emitted in sequencer._operation_done

            data_object = {
                "uuid": unique ID for data
                "operation": uuid of the operation that stored the data
                "name": what the data is called
                "identifier": optional identifier tag to relate this data to something else
                                (like a serial number)
                "description": string description of what the data is
                "value": data itself
                "mimetype": type of object stored
                "size": size of data in bytes
                "info": optional dict of metadata
                "created": timestamp of record
            }

        "created" time usually added by caller - time the record was generated (as opposed
        to now, when the record is stored, in case there is a delay)

        :param list data: data items to store
        :param str evt: event the data came from
        :return: None
        """
        with self.session() as s:
            for data_object in data:
                data_store = {
                    "uuid": data_object.get("uuid"),
                    "operation": data_object.get("operation"),
                    "name": data_object.get("name"),
                    "identifier": data_object.get("identifier"),
                    "description": data_object.get("description"),
                    "value": data_object.get("value"),
                    "mimetype": data_object.get("mimetype"),
                    "size": data_object.get("size"),
                    "info": data_object.get("info"),
                    "created": data_object.get("created"),
                }
                # TODO Fix to allow storing non-binary items in blob - expand as needed
                if type(data_store["value"]) in [int, float, str]:
                    data_store["value"] = "{0}".format(data_store["value"]).encode()
                s.add(DataStorage(**data_store))

    def get_operation_average_duration(self, **kwargs):
        """
        Query the average runtime of every operation from this particular station

        Event emitted in executive.launch_sequence

            kwargs = {
                "stationuuid": unique ID for station
            }

        :param dict kwargs: arguments necessary for query
        :return list: list of tuples - [(operation_id, avg_seconds), ...]
        """
        with self.session() as s:
            avg = (
                s.query(OperationStart.opid, func.avg(OperationEnd.duration))
                .join(OperationEnd, OperationEnd.uuid == OperationStart.uuid)
                .join(SequenceStart, OperationStart.sequence == SequenceStart.uuid)
                .filter(SequenceStart.station == kwargs.get("stationuuid"))
                .filter(OperationEnd.exitcode == 100)
                .group_by(OperationStart.opid)
                .all()
            )
            # Durations stored in milliseconds - convert back to seconds
            avg = [(op, time / 1000.0) for op, time in avg]
            return avg

    # ------------------------------------

    def get_sequences(self, **kwargs):
        """
        Query information about previously run sequences

        Event emitted in SequenceHistoryHandler

            kwargs = {
                "stationuuid": unique ID for station,

                "starttime": (optional) query all sequences after this date/time - given as local timestamp,
                "endtime": (optional) query all sequences before this date/time - given as local timestamp,

                "number": (optional) query this many sequences
            }

        :param dict kwargs: arguments necessary for query
        :return list: list of tuples - [(operation_id, avg_seconds), ...]
        """
        stationuuid = kwargs.get("stationuuid", "none")
        try:
            # Validate stationuuid is a real uuid
            uuidstr.str2uuid(stationuuid)
        except ValueError:
            stationuuid = None

        sequenceuuid = kwargs.get("sequenceuuid", "none")
        try:
            # If sequenceuuid is provided, validate that it is a real uuid
            if sequenceuuid is not None and len(sequenceuuid) == 8:
                # Allow for the truncated length
                uuidstr.str2uuid(sequenceuuid.zfill(32))
            else:
                uuidstr.str2uuid(sequenceuuid)
        except ValueError:
            sequenceuuid = None

        # Set a default start time to 1 week ago if one not provided
        if kwargs.get("starttime", None) is None:
            starttime = get_utc_now() - timedelta(days=7)
        else:
            starttime = local_to_utc(kwargs.get("starttime"))
        starttime = starttime.replace(hour=0, minute=0, second=0)

        # Set a default end time to now if one not provided
        if kwargs.get("endtime", None) is None:
            endtime = get_utc_now()
        else:
            endtime = local_to_utc(kwargs.get("endtime"))
        endtime = endtime.replace(hour=23, minute=59, second=59)

        # If number provided, ensure it is an int, otherwise, 'none' returns all
        number = kwargs.get("number")
        if number is not None:
            number = int(number)

        if sequenceuuid is not None:
            with self.session() as s:
                query = (
                    s.query(
                        SequenceStart.uuid,
                        SequenceStart.created,
                        SequenceEnd.duration,
                        SequenceEnd.passing,
                        SequenceEnd.info,
                    )
                    .join(SequenceEnd, SequenceEnd.uuid == SequenceStart.uuid)
                    .filter(SequenceStart.station == stationuuid)
                    .filter(SequenceStart.created >= starttime)
                    .filter(SequenceEnd.created <= endtime)
                    .filter(SequenceStart.uuid.ilike("{0}%".format(sequenceuuid)))
                    .order_by(desc(SequenceStart.created))
                    .limit(number)
                )
                data = query.all()
        else:
            with self.session() as s:
                query = (
                    s.query(
                        SequenceStart.uuid,
                        SequenceStart.created,
                        SequenceEnd.duration,
                        SequenceEnd.passing,
                        SequenceEnd.info,
                    )
                    .join(SequenceEnd, SequenceEnd.uuid == SequenceStart.uuid)
                    .filter(SequenceStart.station == stationuuid)
                    .filter(SequenceStart.created >= starttime)
                    .filter(SequenceEnd.created <= endtime)
                    .order_by(desc(SequenceStart.created))
                    .limit(number)
                )
                data = query.all()

        # Convert results to dictionaries and convert datetimes to timestamps
        history = []
        for seq in data:
            s = seq._asdict()
            s["created"] = utc_to_local(s["created"]).timestamp()
            history.append(s)

        return history

    def get_sequence_operations(self, **kwargs):
        """
        Query all operations for a specific sequence run

        Event emitted in sequencer/handlers.py

            kwargs = {
                "stationuuid": unique ID for station,
                "sequenceuuid": unique ID for sequence,
            }

        :param dict kwargs: arguments necessary for query
        :return list: list of tuples - [(operation_id, avg_seconds), ...]
        """
        sequenceuuid = kwargs.get("sequenceuuid", "none")
        try:
            # If sequenceuuid is provided, validate that it is a real uuid
            if sequenceuuid is not None and len(sequenceuuid) == 8:
                # Allow for the truncated length
                uuidstr.str2uuid(sequenceuuid.zfill(32))
            else:
                uuidstr.str2uuid(sequenceuuid)
        except ValueError:
            sequenceuuid = None

        with self.session() as s:
            query = (
                s.query(
                    OperationStart.uuid,
                    OperationStart.opid,
                    OperationStart.name,
                    OperationStart.description,
                    OperationEnd.duration,
                    OperationEnd.exitcode,
                    OperationEnd.passing,
                )
                .join(OperationEnd, OperationEnd.uuid == OperationStart.uuid)
                .join(SequenceStart, OperationStart.sequence == SequenceStart.uuid)
                .filter(SequenceStart.station == kwargs.get("stationuuid"))
                .filter(OperationStart.sequence.ilike("{0}%".format(sequenceuuid)))
            )
            return query.all()

    def get_sequence_results(self, **kwargs):
        """
        Query all results for operations for a specific sequence run

        Event emitted in sequencer/handlers.py

            kwargs = {
                "stationuuid": unique ID for station,
                "sequenceuuid": unique ID for sequence,
            }

        :param dict kwargs: arguments necessary for query
        :return list: list of tuples - [(operation_id, avg_seconds), ...]
        """
        sequenceuuid = kwargs.get("sequenceuuid", "none")
        try:
            # If sequenceuuid is provided, validate that it is a real uuid
            if sequenceuuid is not None and len(sequenceuuid) == 8:
                # Allow for the truncated length
                uuidstr.str2uuid(sequenceuuid.zfill(32))
            else:
                uuidstr.str2uuid(sequenceuuid)
        except ValueError:
            sequenceuuid = None

        with self.session() as s:
            query = (
                s.query(
                    OperationStart.opid,
                    Result.uuid,
                    Result.name,
                    Result.description,
                    Result.value,
                    Result.passing,
                    Result.operator,
                    Result.operand2,
                    Result.operand3,
                    Result.created,
                )
                .select_from(SequenceStart)
                .outerjoin(
                    OperationStart, OperationStart.sequence == SequenceStart.uuid
                )
                .outerjoin(Result, Result.operation == OperationStart.uuid)
                .filter(SequenceStart.station == kwargs.get("stationuuid"))
                .filter(OperationStart.sequence.ilike("{0}%".format(sequenceuuid)))
            )
            op_results = query.all()

            # Sort the results by operation
            filtered_results = {}
            for res in op_results:
                o = res._asdict()
                if o["opid"] not in filtered_results:
                    filtered_results[o["opid"]] = []
                if o["uuid"] is not None:
                    o["value"] = float(o["value"])
                    o["created"] = utc_to_local(o["created"]).timestamp()
                    filtered_results[o["opid"]].append(o)

            return filtered_results

    def get_sequence_data(self, **kwargs):
        pass

    # --------------------------------------------------------------------------------------------

    def on_register_new_station(self, data, evt=None):
        """
        Register a new station

        Event emitted in executive

            station = {
                "uuid": unique ID for station (if station doesn't exist)
                "variant":
                "instance":
                "hostname":
                "location":
                "lineid":
            }

        "created" time usually added by caller - time the record was generated (as opposed
        to now, when the record is stored, in case there is a delay)

        :param list data: stations to register
        :param str evt: event the data came from
        :return: None
        """
        with self.session() as s:
            for station in data:
                query = s.query(Station).filter(
                    Station.instance == station.get("instance"),
                    Station.variant == station.get("variant"),
                    Station.macaddress == station.get("mac_address")
                )
                num_stations = query.count()
                if num_stations != 0:
                    # raise Exception("Station '{0}.{1}' already exists".format(
                    #     station.get("variant"), station.get("instance")))
                    log.error(
                        "Station '{0}.{1}' already exists".format(
                            station.get("variant"), station.get("instance")
                        )
                    )
                    return

        with self.session() as s:
            for station in data:
                station_data = {
                    "uuid": station.get("uuid"),
                    "variant": station.get("variant"),
                    "instance": station.get("instance"),
                    "macaddress": station.get("macaddress"),
                    "hostname": station.get("hostname"),
                    "location": station.get("location"),
                    "lineid": station.get("lineid"),
                    "info": station.get("info"),
                    "preferences": station.get("preferences"),
                    "created": station.get("created"),
                }
                s.add(Station(**station_data))

    def on_update_station(self, data, evt=None):
        """

        :param list data: stations to update
        :param str evt: event the data came from
        :return: None
        """
        for new_station_info in data:
            with self.session() as s:
                query = s.query(Station).filter(
                    Station.instance == new_station_info.get("instance"),
                    Station.variant == new_station_info.get("variant")
                )
                old_station_info = query.first()
                if "hostname" in new_station_info:
                    old_station_info.hostname = new_station_info["hostname"]
                if "macaddress" in new_station_info:
                    old_station_info.macaddress = new_station_info["macaddress"]
                if "location" in new_station_info:
                    old_station_info.location = new_station_info["location"]
                if "lineid" in new_station_info:
                    old_station_info.lineid = new_station_info["lineid"]
                if "preferences" in new_station_info:
                    old_station_info.preferences = simplejson.dumps(new_station_info["preferences"])
                if "info" in new_station_info:
                    old_station_info.info = simplejson.dumps(new_station_info["info"])

                old_station_info.updated = get_utc_now()
        log.info('Station info has been updated')

    def get_station_data(self, instance:str, hostname:str, mac_address:str, **_kwargs):
        """
        :return Station: Station object if it exists
        """
        with self.session() as s:
            query = s.query(Station).filter(
                Station.instance == instance,
                Station.hostname == hostname,
                Station.macaddress == mac_address
            )
            return query.first()

    # --------------------------------------------------------------------------------------------

    def on_log_data(self, data, evt=None):
        """
        Store log information; called on log event

        Event emitted in log._publish_log_message:

            log_data = {
                "stream": type of log event
                "message": content of log event
                "debug_level": numeric debug level (if stream is debug)
                "data": log data attachment (string of exception usually)
                "stack_trace": text of stack trace (for stream exception)
                "pid": process id where event happened
                "caller": method that created the log
            }

        "created" time usually added by caller - time the record was generated (as opposed
        to now, when the record is stored, in case there is a delay)

        :param list data: log data to store
        :param str evt: event the data came from
        :return: None
        """
        with self.session() as s:
            for log_data in data:
                msg = {
                    "stream": log_data.get("stream"),
                    "message": log_data.get("message"),
                    "created": log_data.get("created"),
                }
                if log_data.get("stream") == "debug" and self._log_level:
                    if log_data.get("debug_level") > self._log_level:
                        continue
                s.add(Logging(**msg))

    def get_log_data(self, start_time, end_time, stream=None, **_kwargs):
        """
        Query stored log data by start and end time

        :param datetime start_time: local time start time
        :param datetime end_time: local time end time
        :param str stream: log stream - None if all are desired
        :param _kwargs: extra keyword arguments
        :return list: Logging objects in time range
        """
        start_time = local_to_utc(start_time)
        end_time = local_to_utc(end_time)

        with self.session() as s:
            # Data of a stream type (all if unspecified) between start and end times
            if stream is not None:
                query = s.query(Logging).filter(
                    Logging.created.between(start_time, end_time),
                    Logging.stream == stream,
                )
            else:
                query = s.query(Logging).filter(
                    Logging.created.between(start_time, end_time)
                )
            return query.all()

    # --------------------------------------------------------------------------------------------

    def on_maintenance_data(self, **kwargs):
        with self.session() as s:
            s.add(Maintenance(**kwargs))

    def get_maintenance_data(self, data):
        pass


class DataHandler(ExecutiveHandler):
    def initialize(self, **kwargs):
        self.tool = kwargs.get("tool")  # type:StationStorage

    def get(self):
        # tbl = self.get_arguments("table")
        # data = self.tool.read_table(tbl[0])
        data = self.tool.read_logs()
        self.write(simplejson.dumps(data))


class InfoHandler(ExecutiveHandler):
    def initialize(self, **kwargs):
        self.tool = kwargs.get("tool")  # type:StationStorage

    def get(self):
        data = self.tool.get_info()
        self.write(simplejson.dumps(data))


if __name__ == "__main__":
    args = {
        "tool_type": "station_storage",
        "name": "Station Storage",
        "tool_id": "storage",
        "debug": 3,
        "dev": False,
    }
    ss = StationStorage({}, **args)
    ss.initialize()

    """
    args = {
        "stationuuid": "ec155e62d97211e99bce68f728739436",
        "starttime": None,
        "endtime": None,
        "number": 4
    }
    seqs = ss.get_sequences(**args)
    for seq in seqs:
        print("Sequence '{0:.8}' ran on {1} for {2}s and resulted in a {3}".
              format(seq.uuid, utc_to_local(seq.created),
                     seq.duration / 1000.0, seq.passing))
    """

    args = {
        "stationuuid": "ec155e62d97211e99bce68f728739436",
        "sequenceuuid": "f68d5dd0d98611e9ac4268f728739436",
    }
    ops = ss.get_sequence_operations(**args)
    for operation in ops:
        print(
            "{0} for {1}s and exited with {2}".format(
                operation.opid, operation.duration / 1000.0, operation.exitcode
            )
        )
