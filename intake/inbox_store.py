import json
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from intake.manifest import BatchManifest
from intake.package_checks import check_arrival
from issue.envelope import PackageEnvelope, decode_package


@dataclass(frozen=True, slots=True)
class ReceiptRecord:
    receipt_id: str
    envelope: PackageEnvelope
    raw: bytes


class InboxStore:
    def __init__(self, path: str | Path):
        self.path = path

    def initialize(self, manifests: Iterable[BatchManifest] = ()) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''
                CREATE TABLE IF NOT EXISTS manifests (
                    batch TEXT PRIMARY KEY, stations TEXT NOT NULL
                )
            ''')
            db.execute('''
                CREATE TABLE IF NOT EXISTS arrivals (
                    id TEXT PRIMARY KEY, freeze_id TEXT NOT NULL UNIQUE, batch TEXT NOT NULL,
                    station TEXT NOT NULL, revision_id TEXT NOT NULL, raw BLOB NOT NULL
                )
            ''')
            for manifest in manifests:
                db.execute('''
                    INSERT INTO manifests (batch, stations) VALUES (?, ?)
                    ON CONFLICT (batch) DO NOTHING
                ''', (manifest.batch, json.dumps(manifest.to_mapping())))

    @staticmethod
    def _read_manifest(db: sqlite3.Connection, batch: str) -> BatchManifest:
        row = db.execute('SELECT stations FROM manifests WHERE batch = ?', (batch,)).fetchone()
        if row is None:
            raise LookupError(f'unknown batch manifest: {batch}')
        return BatchManifest.from_mapping(batch, json.loads(row[0]))

    def get_manifest(self, batch: str) -> BatchManifest:
        with closing(sqlite3.connect(self.path)) as db:
            return self._read_manifest(db, batch)

    def record_arrival(self, batch: str, station: str, raw: bytes) -> ReceiptRecord:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            envelope = check_arrival(self._read_manifest(db, batch), station, raw)
            binding = (envelope.batch, envelope.station, envelope.revision_id, raw)
            existing = db.execute('''
                SELECT id, batch, station, revision_id, raw FROM arrivals WHERE freeze_id = ?
            ''', (envelope.freeze_id,)).fetchone()
            if existing is not None:
                if existing[1:] != binding:
                    raise ValueError('freeze number is already bound to different bytes or provenance')
                receipt_id = existing[0]
            else:
                receipt_id = f'arr-{uuid4().hex}'
                db.execute('INSERT INTO arrivals VALUES (?, ?, ?, ?, ?, ?)',
                           (receipt_id, envelope.freeze_id, *binding))
        return ReceiptRecord(receipt_id, envelope, raw)

    def find_receipt(self, receipt_id: str) -> ReceiptRecord | None:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('''
                SELECT freeze_id, batch, station, revision_id, raw FROM arrivals WHERE id = ?
            ''', (receipt_id,)).fetchone()
        if row is None:
            return None
        freeze_id, batch, station, revision_id, raw = row
        envelope = decode_package(raw)
        if (envelope.freeze_id, envelope.batch, envelope.station, envelope.revision_id) != (
            freeze_id, batch, station, revision_id
        ):
            raise ValueError('stored receipt binding does not match its package')
        return ReceiptRecord(receipt_id, envelope, raw)
