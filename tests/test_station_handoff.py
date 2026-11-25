import json

from issue.dispatch import freeze_package, get_package
from issue.issue_store import IssueStore
from survey.capture import record_revision
from survey.revision_store import RevisionStore
from tests.support import WorkspaceCase, fetch


class StationHandoffTests(WorkspaceCase):
    def test_freeze_historical_revision_and_reissue_original_bytes(self):
        star, chain, south = self.stage()
        path = self.workspace.station('north')
        revisions = RevisionStore(path)
        first = revisions.get_revision(star.revision_id)
        corrected = revisions.get_current_revision('north', self.batch)
        self.assertIsNone(first.parent_id)
        self.assertEqual(corrected.revision_id, chain.revision_id)
        self.assertEqual(corrected.parent_id, first.revision_id)
        self.assertEqual(first.wiring.to_line_table(), self.north['tables']['initial'])
        self.assertEqual(corrected.wiring.to_line_table(), self.north['tables']['corrected'])
        self.assertNotEqual(star.freeze_id, chain.freeze_id)

        original, later = (json.loads(item.raw) for item in (star, chain))
        self.assertEqual(original['revision_id'], star.revision_id)
        self.assertEqual(later['revision_id'], chain.revision_id)
        self.assertNotEqual(original['evidence'], later['evidence'])
        self.assertNotIn(b'junction-n17', star.raw)
        self.assertNotIn(b'n-arm-a', star.raw)
        self.assertEqual(json.loads(south.raw)['station'], 'south')
        self.assertEqual(get_package(IssueStore(path), star.freeze_id), star)
        self.assertEqual(fetch(path, 'SELECT COUNT(*) FROM packages'), [(2,)])

    def test_wrong_station_unknown_revision_and_unknown_package(self):
        revision_id = self.record('north')
        path = self.workspace.station('north')
        issues = IssueStore(path)
        with self.assertRaises(ValueError):
            freeze_package(RevisionStore(path), issues, 'south', revision_id)
        with self.assertRaises(LookupError):
            freeze_package(RevisionStore(path), issues, 'north', 'missing-revision')
        with self.assertRaises(LookupError):
            get_package(issues, 'missing-package')
        self.assertEqual(fetch(path, 'SELECT COUNT(*) FROM packages'), [(0,)])

    def test_invalid_corrections_preserve_current_and_original(self):
        original = self.record('north')
        path = self.workspace.station('north')
        store = RevisionStore(path)
        bad_tables = {
            'unknown_endpoint': {'junctions': [], 'wires': [['bad', 'A', 'X']]},
            'unreachable_junction': {'junctions': ['X', 'Y'], 'wires': [['bad', 'X', 'Y']]},
            'duplicate_wire': {'junctions': [], 'wires': [['dup', 'A', 'B'], ['dup', 'B', 'C']]},
        }
        for name, table in bad_tables.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    record_revision(store, 'north', self.batch, original, self.terminals, table)
                self.assertEqual(store.get_current_revision('north', self.batch).revision_id, original)
                self.assertEqual(fetch(path, 'SELECT COUNT(*) FROM revisions'), [(1,)])
        old = self.freeze('north', original)
        self.assertEqual(json.loads(old.raw)['revision_id'], original)
        self.assertEqual(get_package(IssueStore(path), old.freeze_id).raw, old.raw)

    def test_duplicate_first_version_and_foreign_parents_rejected(self):
        original = self.record('north')
        path = self.workspace.station('north')
        store = RevisionStore(path)
        table = self.north['tables']['corrected']
        for station, batch, parent in (('north', self.batch, None),
                                       ('south', self.batch, original),
                                       ('north', 'other-batch', original)):
            with self.subTest(station=station, batch=batch, parent=parent):
                with self.assertRaises(ValueError):
                    record_revision(store, station, batch, parent, self.terminals, table)
        with self.assertRaises(LookupError):
            record_revision(store, 'north', self.batch, 'unknown', self.terminals, table)
        self.assertEqual(fetch(path, 'SELECT COUNT(*) FROM revisions'), [(1,)])
        self.assertEqual(store.get_current_revision('north', self.batch).revision_id, original)
