import json
import sqlite3
from contextlib import closing
from pathlib import Path

from survey.revisions import Revision
from survey.terminals import validate_terminal_set
from survey.wiring import validate_wiring


class RevisionStore:
    def __init__(self, path: str | Path):
        self.path = path

    def initialize(self) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''
                CREATE TABLE IF NOT EXISTS revisions (
                    id TEXT PRIMARY KEY, station TEXT NOT NULL, batch TEXT NOT NULL,
                    parent_id TEXT, terminals TEXT NOT NULL, line_table TEXT NOT NULL
                )
            ''')
            db.execute('''
                CREATE TABLE IF NOT EXISTS current_revisions (
                    station TEXT NOT NULL, batch TEXT NOT NULL, revision_id TEXT NOT NULL,
                    PRIMARY KEY (station, batch)
                )
            ''')

    def append_revision(self, revision: Revision) -> str:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if revision.parent_id is None:
                current = db.execute(
                    'SELECT 1 FROM current_revisions WHERE station = ? AND batch = ?',
                    (revision.station, revision.batch),
                ).fetchone()
                if current is not None:
                    raise ValueError('station and batch already have an initial revision')
            else:
                owner = db.execute(
                    'SELECT station, batch FROM revisions WHERE id = ?', (revision.parent_id,)
                ).fetchone()
                if owner is None:
                    raise LookupError(f'unknown parent revision: {revision.parent_id}')
                if owner != (revision.station, revision.batch):
                    raise ValueError('parent revision belongs to a different station or batch')

            db.execute(
                'INSERT INTO revisions VALUES (?, ?, ?, ?, ?, ?)',
                (revision.revision_id, revision.station, revision.batch, revision.parent_id,
                 json.dumps(revision.terminals.names), json.dumps(revision.wiring.to_line_table())),
            )
            db.execute('''
                INSERT INTO current_revisions (station, batch, revision_id) VALUES (?, ?, ?)
                ON CONFLICT (station, batch) DO UPDATE SET revision_id = excluded.revision_id
            ''', (revision.station, revision.batch, revision.revision_id))
        return revision.revision_id

    def get_revision(self, revision_id: str) -> Revision:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('SELECT * FROM revisions WHERE id = ?', (revision_id,)).fetchone()
        if row is None:
            raise LookupError(f'unknown revision: {revision_id}')
        return self._restore(row)

    def get_current_revision(self, station: str, batch: str) -> Revision:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('''
                SELECT revisions.* FROM current_revisions
                JOIN revisions ON revisions.id = current_revisions.revision_id
                WHERE current_revisions.station = ? AND current_revisions.batch = ?
            ''', (station, batch)).fetchone()
        if row is None:
            raise LookupError(f'no revision for {station} in {batch}')
        return self._restore(row)

    @staticmethod
    def _restore(row: tuple) -> Revision:
        revision_id, station, batch, parent_id, terminal_json, table_json = row
        terminals = validate_terminal_set(json.loads(terminal_json))
        wiring = validate_wiring(terminals, json.loads(table_json))
        return Revision(revision_id, station, batch, parent_id, terminals, wiring)
