from pymongo.mongo_client import MongoClient
from pymongo_greenlet import GreenletClient, patch_pymongo, unpatch_pymongo
from pymongo.read_preferences import ReadPreference
import pymongo.topology
import collections
from tornado import ioloop

__all__ = ['ConnectionError', 'connect', 'set_default_db', 'SlaveOkSettings']

MongoConnections = collections.namedtuple('MongoConnections',
                                           ['sync', 'async'])

SlaveOkSettings = collections.namedtuple('SlaveOkSettings',
                                         ['read_pref', 'tags'])

_connections = {}
_dbs = {}
_db_to_conn = {}
_default_db = 'sweeper'
_slave_ok_settings = {
    False: SlaveOkSettings(ReadPreference.PRIMARY_PREFERRED, [{}]),
    True: SlaveOkSettings(ReadPreference.SECONDARY_PREFERRED, [{}])
}

class ConnectionError(Exception):
    pass


def _get_db(db_name='test', reconnect=False, allow_async=True):
    global _dbs, _connections, _db_to_conn

    if not db_name:
        db_name = _default_db

    if db_name not in _dbs:
        if not _db_to_conn:
            conn_name = None

        else:
            if db_name not in _db_to_conn:
                return None

            conn_name = _db_to_conn[db_name]

        if conn_name not in _connections:
            return None

        conn = _connections[conn_name]
        _dbs[db_name] = (conn.sync[db_name],
                         conn.async[db_name] if conn.async else None)

    sync, async = _dbs[db_name]

    return async if allow_async and async else sync

def _get_slave_ok(slave_ok):
    return _slave_ok_settings[slave_ok]


def connect(host='localhost', conn_name=None, db_names=None, allow_async=False,
            slave_ok_settings=None, **kwargs):
    global _connections, _db_to_conn, _slave_ok_settings

    # Connect to the database if not already connected
    if conn_name not in _connections:
        try:
            if allow_async:
                io_loop = kwargs.pop('io_loop', ioloop.IOLoop.instance())
                patch_pymongo(io_loop)
                async_conn = GreenletClient.sync_connect(host, **kwargs)
                unpatch_pymongo()
            else:
                async_conn = None
            kwargs.pop('io_loop', None)

            sync_conn = MongoClient(host, **kwargs)

            _connections[conn_name] = MongoConnections(sync_conn, async_conn)
        except Exception as e:
            raise ConnectionError('Cannot connect to the database: %s' % str(e))

        if db_names:
            for db in db_names:
                _db_to_conn[db] = conn_name

        if slave_ok_settings:
            _slave_ok_settings = slave_ok_settings

    return _connections[conn_name]

def set_default_db(db):
    global _default_db

    _default_db = db
