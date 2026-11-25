import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from review.counting import ReviewCounts
from review.parents import BoundParents, ParentReference
from survey.terminals import validate_name


@dataclass(frozen=True, slots=True)
class SignedReport:
    report_id: str
    batch: str
    parents: tuple[ParentReference, ParentReference]
    list_id: str
    selected: tuple[str, str]
    total: int
    together: int
    receipt: bytes


def _canonical_bytes(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


class ReportStore:
    def __init__(self, path: str | Path):
        self.path = path

    def initialize(self) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY, payload BLOB NOT NULL
                )
            ''')
            db.execute('''
                CREATE TABLE IF NOT EXISTS report_receipts (
                    report_id TEXT PRIMARY KEY REFERENCES reports (id), raw BLOB NOT NULL
                )
            ''')

    def commit_report(self, report_id: str, parents: BoundParents, counts: ReviewCounts) -> SignedReport:
        validate_name(report_id, 'report number')
        references = parents.references()
        link_list = parents.link_list
        payload = _canonical_bytes({
            'report_id': report_id,
            'batch': link_list.batch,
            'parents': [asdict(parent) for parent in references],
            'list_id': link_list.list_id,
            'selected': parents.selected,
            'total': hex(counts.total),
            'together': hex(counts.together),
        })
        receipt = _canonical_bytes({'report_id': report_id, 'report_sha256': sha256(payload).hexdigest()})
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('PRAGMA foreign_keys = ON')
            db.execute('INSERT INTO reports (id, payload) VALUES (?, ?)', (report_id, payload))
            db.execute('INSERT INTO report_receipts (report_id, raw) VALUES (?, ?)', (report_id, receipt))
        return SignedReport(report_id, link_list.batch, references, link_list.list_id,
                            parents.selected, counts.total, counts.together, receipt)

    def find_report(self, report_id: str) -> SignedReport | None:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('''
                SELECT reports.payload, report_receipts.raw FROM reports
                JOIN report_receipts ON report_receipts.report_id = reports.id
                WHERE reports.id = ?
            ''', (report_id,)).fetchone()
        if row is None:
            return None
        payload, receipt = row
        document = json.loads(payload)
        parents = tuple(ParentReference(**parent) for parent in document['parents'])
        selected = tuple(document['selected'])
        return SignedReport(document['report_id'], document['batch'], parents, document['list_id'],
                            selected, int(document['total'], 16), int(document['together'], 16), receipt)
