__author__ = "h5vx"
import sqlite3
import threading
import queue
from distutils.version import LooseVersion


SQL_INIT_SCRIPT = """
    CREATE TABLE IF NOT EXISTS hosts (
        hostname TEXT PRIMARY KEY,
        type TEXT,
        reason TEXT,
        latency REAL,
        added DATE,
        updated DATE
    );
"""

class DBThread(threading.Thread):
    SQL_ADD_HOST = """
        INSERT INTO hosts (hostname, type, reason, latency, added, updated)
        VALUES (?,?,?,?,?,0)
        ON CONFLICT(hostname)
        DO UPDATE SET 
            type=excluded.type,
            reason=excluded.reason,
            latency=excluded.latency,
            updated=excluded.added
    """

    def __init__(self, dbname):
        threading.Thread.__init__(self)
        self.q = queue.Queue()
        self.working = True
        self.name = "db"
        self.dbname = dbname

    def _add_host_entry(self, host, dbc):
        dbc.execute(self.SQL_ADD_HOST, (
            host.get('host', ""),
            host.get('type', ""),
            host.get('reason', ""),
            host.get('latency', -1),
            host.get('updated', 0)
        ))

    def run(self):
        db = sqlite3.connect(self.dbname)
        dbc = db.cursor()
        dbc.execute(SQL_INIT_SCRIPT)
        self.working = True
        while self.working or self.q.qsize() > 0:
            try:
                host = self.q.get(timeout=1)
            except queue.Empty:
                pass
            else:
                self._add_host_entry(host, dbc)
        dbc.close()
        db.commit()
        db.close()

    def stop(self):
        self.working = False


# Check that SQLite have UPSERT clause (added in 3.24.0)
if LooseVersion(sqlite3.sqlite_version) < LooseVersion('3.24.0'):
    # No UPSERT, we need to perform some monkey patching for DBThread
    class DBThreadWithoutUpsert(DBThread):
        SQL_ADD_HOST = """           
            INSERT INTO hosts (hostname, type, reason, latency, added, updated)
            VALUES (:hostname,:type,:reason,:latency,:added,0);
        """

        SQL_UPDATE_HOST = """
            UPDATE hosts SET 
                type=:type,
                reason=:reason,
                latency=:latency,
                updated=:added
            WHERE hostname=:hostname;
        """

        def _add_host_entry(self, host, dbc):
            params = {
                'hostname': host.get('host', ""),
                'type': host.get('type', ""),
                'reason': host.get('reason', ""),
                'latency': host.get('latency', -1),
                'added': host.get('updated', 0)
            }
            try:
                dbc.execute(self.SQL_ADD_HOST, params)
            except sqlite3.IntegrityError:  # Nothing inserted, entry exists
                dbc.execute(self.SQL_UPDATE_HOST, params)

    DBThread = DBThreadWithoutUpsert
