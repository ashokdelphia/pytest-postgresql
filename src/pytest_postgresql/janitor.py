"""Database Janitor."""
from contextlib import contextmanager
from types import TracebackType
from typing import TypeVar, Union, Optional, Type, Any

from pkg_resources import parse_version
Version = type(parse_version('1'))  # pylint:disable=invalid-name

try:
    import psycopg2
    try:
        from psycopg2._psycopg import cursor
    except ImportError:
        from psycopg2cffi._impl.cursor import Cursor as cursor
except ImportError:
    psycopg2 = False
    # if there's no postgres, just go with the flow.
    cursor = Any  # pylint:disable=invalid-name

DatabaseJanitorType = TypeVar("DatabaseJanitorType", bound="DatabaseJanitor")


class DatabaseJanitor:
    """Manage database state for specific tasks."""

    def __init__(
            self,
            user: str,
            host: str,
            port: str,
            db_name: str,
            version: Union[str, float, Version]
    ) -> None:
        """
        Initialize janitor.

        :param user: postgresql username
        :param host: postgresql host
        :param port: postgresql port
        :param db_name: database name
        :param version: postgresql version number
        """
        self.user = user
        self.host = host
        self.port = port
        self.db_name = db_name
        if not isinstance(version, Version):
            self.version = parse_version(str(version))
        else:
            self.version = version

    def init(self) -> None:
        """Create database in postgresql."""
        with self.cursor() as cur:
            cur.execute('CREATE DATABASE "{}";'.format(self.db_name))

    def drop(self) -> None:
        """Drop database in postgresql."""
        # We cannot drop the database while there are connections to it, so we
        # terminate all connections first while not allowing new connections.
        if self.version >= parse_version('9.2'):
            pid_column = 'pid'
        else:
            pid_column = 'procpid'
        with self.cursor() as cur:
            cur.execute(
                'UPDATE pg_database SET datallowconn=false WHERE datname = %s;',
                (self.db_name,))
            cur.execute(
                'SELECT pg_terminate_backend(pg_stat_activity.{})'
                'FROM pg_stat_activity '
                'WHERE pg_stat_activity.datname = %s;'.format(pid_column),
                (self.db_name,))
            cur.execute('DROP DATABASE IF EXISTS "{}";'.format(self.db_name))

    @contextmanager
    def cursor(self) -> cursor:
        """Return postgresql cursor."""
        conn = psycopg2.connect(
            dbname='postgres',
            user=self.user,
            host=self.host,
            port=self.port,
        )
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()
            conn.close()

    def __enter__(self: DatabaseJanitorType) -> DatabaseJanitorType:
        self.init()
        return self

    def __exit__(
            self: DatabaseJanitorType,
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType]) -> None:
        self.drop()
