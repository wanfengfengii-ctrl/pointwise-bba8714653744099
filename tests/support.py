import json
import sqlite3
import unittest
from contextlib import closing
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory

from intake.inbox_store import InboxStore
from intake.manifest import BatchManifest
from intake.receipts import receive_package
from issue.dispatch import freeze_package
from issue.issue_store import IssueStore
from links.catalog_store import CatalogStore
from links.fixed_list import freeze_links
from review.cli import initialize_workspace
from review.publication import issue_report
from review.report_store import ReportStore
from survey.capture import record_revision
from survey.revision_store import RevisionStore


def sample(name):
    folder = Path(__file__).resolve().parents[1] / 'samples'
    return json.loads((folder / f'{name}.json').read_text(encoding='utf-8'))


def fetch(path, sql, params=()):
    with closing(sqlite3.connect(path)) as db:
        return db.execute(sql, params).fetchall()


def execute(path, sql, params=()):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(sql, params)


def link(number, a, b):
    return {'id': number, 'a': ['north', a], 'b': ['south', b]}


SPLIT = (('A',), ('B',), ('C',))
CONNECTED = (('A', 'B', 'C'),)
STAR_FORESTS = [(SPLIT, 3), ((('A', 'B'), ('C',)), 1), ((('A', 'C'), ('B',)), 1),
                ((('A',), ('B', 'C')), 1), (CONNECTED, 1)]
CHAIN_FORESTS = [(SPLIT, 1), ((('A', 'B'), ('C',)), 1), ((('A',), ('B', 'C')), 1), (CONNECTED, 1)]


def independent_package(batch, station, freeze_id, revision_id, forests, terminals=('A', 'B', 'C')):
    # Write the wire format directly, without calling an issuance or encoding helper.
    rows = [{'groups': groups, 'count': format(count, '#x')} for groups, count in forests]
    return json.dumps({'version': 1, 'batch': batch, 'station': station, 'freeze_id': freeze_id,
                       'revision_id': revision_id, 'terminals': terminals,
                       'evidence': {'forests': rows}}).encode('utf-8')


def enumerate_wirings(terminals, site_tables, link_rows, selected):
    """Independently count raw line subsets in four bins by specified-wire use."""
    vertices = set(terminals)
    edges = []
    for station, table in site_tables.items():
        private = {name: (station, name) for name in table['junctions']}
        vertices.update(private.values())
        for number, a, b in table['wires']:
            edges.append(((station, number), private.get(a, a), private.get(b, b)))
    spare = object()
    edges.extend(((spare, row['id']), row['a'][1], row['b'][1]) for row in link_rows)
    bins = [0, 0, 0, 0]
    for choice in combinations(edges, len(vertices) - 1):
        neighbours = {vertex: set() for vertex in vertices}
        identities = set()
        for identity, a, b in choice:
            neighbours[a].add(b)
            neighbours[b].add(a)
            identities.add(identity)
        # A connected multigraph on n vertices with n-1 chosen edges is a tree.
        seen = {terminals[0]}
        pending = [terminals[0]]
        while pending:
            for neighbour in neighbours[pending.pop()] - seen:
                seen.add(neighbour)
                pending.append(neighbour)
        if seen == vertices:
            first, second = ((spare, name) in identities for name in selected)
            bins[int(first) + 2 * int(second)] += 1
    return bins


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        root = self.enterContext(TemporaryDirectory(prefix='wiring-test-'))
        self.north = sample('north')
        self.south = sample('south')
        self.settings = sample('center')
        self.batch = self.settings['batch']
        self.terminals = self.north['terminals']
        self.manifest = BatchManifest.from_mapping(self.batch, self.settings['stations'])
        self.workspace = initialize_workspace(root, (self.manifest,))
        self.inbox = InboxStore(self.workspace.center)
        self.catalog = CatalogStore(self.workspace.center)
        self.reports = ReportStore(self.workspace.center)

    def record(self, station, parent=None, table='initial'):
        survey = self.north if station == 'north' else self.south
        return record_revision(RevisionStore(self.workspace.station(station)), station, self.batch,
                               parent, survey['terminals'], survey['tables'][table])

    def freeze(self, station, revision_id):
        db = self.workspace.station(station)
        return freeze_package(RevisionStore(db), IssueStore(db), station, revision_id)

    def stage(self):
        original = self.record('north')
        corrected = self.record('north', original, 'corrected')
        south = self.record('south')
        return (self.freeze('north', original), self.freeze('north', corrected), self.freeze('south', south))

    def admit(self, *packages):
        return tuple(receive_package(self.inbox, self.batch, item.station, item.raw) for item in packages)

    def link_list(self, rows=None):
        return freeze_links(self.inbox, self.catalog, self.batch,
                            self.settings['links'] if rows is None else rows)

    def publish(self, receipt_ids, list_id, selected=('p', 'q')):
        return issue_report(self.inbox, self.catalog, self.reports, receipt_ids, list_id, selected)

    def go_offline(self):
        for station in ('north', 'south'):
            path = self.workspace.station(station)
            path.unlink()
            self.assertFalse(path.exists())

    def center_counts(self):
        return fetch(self.workspace.center, '''
            SELECT (SELECT COUNT(*) FROM arrivals), (SELECT COUNT(*) FROM link_lists),
                   (SELECT COUNT(*) FROM reports), (SELECT COUNT(*) FROM report_receipts)
        ''')[0]
