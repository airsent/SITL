"""Bounded SQLite event history for ASC transitions. Monitoring only.

No flight-control imports, network services or command execution. Database is
opt-in via ASC_SQLITE_PATH and event records contain no raw telemetry or images.
"""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time

@contextmanager
def connect(path):
    db=sqlite3.connect(path,timeout=2.0)
    try:
        with db:
            yield db
    finally:
        db.close()

class ASCEventStore:
    def __init__(self,path,max_events=20000):
        self.path=Path(path)
        self.max_events=max(100,int(max_events))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with connect(self.path) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('''CREATE TABLE IF NOT EXISTS transitions (
                id INTEGER PRIMARY KEY,
                recorded_at REAL NOT NULL,
                sequence INTEGER NOT NULL,
                check_id TEXT NOT NULL,
                previous TEXT NOT NULL,
                current TEXT NOT NULL,
                reason TEXT NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS asc_events_time ON transitions(recorded_at)')

    def write_transitions(self,sequence,transitions):
        if not transitions:
            return
        now=time.time()
        rows=[(now,sequence,t['id'],t['before'],t['after'],str(t['reason'])[:512]) for t in transitions]
        with connect(self.path) as db:
            db.executemany('''INSERT INTO transitions
                (recorded_at,sequence,check_id,previous,current,reason) VALUES (?,?,?,?,?,?)''',rows)
            db.execute('''DELETE FROM transitions WHERE id IN (
                SELECT id FROM transitions ORDER BY id DESC LIMIT -1 OFFSET ?)''',(self.max_events,))

    def recent(self,limit=100):
        with connect(self.path) as db:
            rows=db.execute('''SELECT recorded_at,sequence,check_id,previous,current,reason
                FROM transitions ORDER BY id DESC LIMIT ?''',(max(1,min(int(limit),500)),)).fetchall()
        return [dict(zip(('timestamp','sequence','check_id','before','after','reason'),r)) for r in rows]
