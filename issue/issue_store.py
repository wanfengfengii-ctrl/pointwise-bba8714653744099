import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from issue.envelope import PackageEnvelope, encode_package


@dataclass(frozen=True, slots=True)
class IssuedPackage:
    freeze_id: str
    batch: str
    station: str
    revision_id: str
    raw: bytes


class IssueStore:
    def __init__(self, path: str | Path):
        self.path = path

    def initialize(self) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('''
                CREATE TABLE IF NOT EXISTS packages (
                    id TEXT PRIMARY KEY, batch TEXT NOT NULL, station TEXT NOT NULL,
                    revision_id TEXT NOT NULL, raw BLOB NOT NULL
                )
            ''')

    def save_package(self, envelope: PackageEnvelope) -> IssuedPackage:
        item = IssuedPackage(
            envelope.freeze_id, envelope.batch, envelope.station,
            envelope.revision_id, encode_package(envelope),
        )
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                'INSERT INTO packages VALUES (?, ?, ?, ?, ?)',
                (item.freeze_id, item.batch, item.station, item.revision_id, item.raw),
            )
        return item

    def find_package(self, freeze_id: str) -> IssuedPackage | None:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('SELECT * FROM packages WHERE id = ?', (freeze_id,)).fetchone()
        return IssuedPackage(*row) if row is not None else None
