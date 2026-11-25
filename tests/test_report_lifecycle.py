import json
import sqlite3
from hashlib import sha256

from intake.inbox_store import InboxStore
from intake.manifest import BatchManifest
from review.cli import initialize_workspace
from review.counting import count_review
from review.parents import bind_review_parents
from review.publication import get_report
from review.report_store import ReportStore
from review.request import validate_request
from survey.revision_store import RevisionStore
from tests.support import WorkspaceCase, execute, fetch, link


class ReportLifecycleTests(WorkspaceCase):
    def test_original_report_and_receipt_survive_correction_and_reopen(self):
        first_revision = self.record('north')
        north = self.freeze('north', first_revision)
        south = self.freeze('south', self.record('south'))
        south_id, north_id = self.admit(south, north)
        list_id = self.link_list()
        original = self.publish((south_id, north_id), list_id, ('q', 'p'))
        self.assertEqual((original.total, original.together), (8, 3))
        self.assertEqual(original.selected, ('q', 'p'))
        self.assertEqual([(parent.station, parent.receipt_id, parent.freeze_id) for parent in original.parents],
                         [('south', south_id, south.freeze_id), ('north', north_id, north.freeze_id)])

        payload, = fetch(self.workspace.center, 'SELECT payload FROM reports WHERE id = ?', (original.report_id,))
        self.assertEqual(json.loads(original.receipt), {'report_id': original.report_id,
                                                       'report_sha256': sha256(payload[0]).hexdigest()})
        corrected_revision = self.record('north', first_revision, 'corrected')
        corrected = self.freeze('north', corrected_revision)
        corrected_id, = self.admit(corrected)
        new_list = self.link_list([link('p', 'A', 'B'), link('q', 'B', 'C'), link('r', 'A', 'C')])
        self.go_offline()
        changed = self.publish((corrected_id, south_id), new_list)
        reopened = ReportStore(self.workspace.center)
        self.assertEqual(changed.list_id, new_list)
        self.assertEqual(changed.parents[0].revision_id, corrected_revision)
        returned = get_report(reopened, original.report_id)
        self.assertEqual(returned, original)
        self.assertEqual(returned.list_id, list_id)
        self.assertEqual(returned.receipt, original.receipt)
        with self.assertRaises(LookupError):
            get_report(reopened, 'report-not-issued')

    def test_reinitialize_keeps_user_manifest_changes_and_existing_records(self):
        star, chain, south = self.stage()
        ids = self.admit(star, south)
        list_id = self.link_list()
        report = self.publish(ids, list_id)
        before = self.center_counts()
        replacement = {'north': ['A', 'B', 'Z'], 'south': ['A', 'B', 'Z']}
        execute(self.workspace.center, 'UPDATE manifests SET stations = ? WHERE batch = ?',
                (json.dumps(replacement), self.batch))
        added = BatchManifest.from_mapping('another-shift', self.settings['stations'])
        initialize_workspace(self.workspace.root, (self.manifest, added))
        reopened_inbox = InboxStore(self.workspace.center)
        self.assertEqual(reopened_inbox.get_manifest(self.batch).to_mapping(),
                         {key: tuple(names) for key, names in replacement.items()})
        self.assertEqual(reopened_inbox.get_manifest(added.batch), added)
        self.assertEqual(self.center_counts(), before)
        current = RevisionStore(self.workspace.station('north')).get_current_revision('north', self.batch)
        self.assertEqual(current.revision_id, chain.revision_id)
        self.assertEqual(get_report(ReportStore(self.workspace.center), report.report_id), report)

    def test_receipt_insert_failure_rolls_back_pending_report(self):
        star, _, south = self.stage()
        ids = self.admit(star, south)
        list_id = self.link_list()
        self.go_offline()
        old = self.publish(ids, list_id)
        before = self.center_counts()
        execute(self.workspace.center, '''
            CREATE TRIGGER reject_next_receipt BEFORE INSERT ON report_receipts
            BEGIN
                SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM reports WHERE id = NEW.report_id)
                    THEN RAISE(ABORT, 'report has not been inserted') END;
                SELECT RAISE(ABORT, 'receipt write failed after report insert');
            END
        ''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'receipt write failed after report insert'):
            self.publish(ids[::-1], list_id)
        request = validate_request(ids[::-1], list_id, ('p', 'q'))
        parents = bind_review_parents(self.inbox, self.catalog, request)
        candidate = 'report-known-failed-candidate'
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'receipt write failed after report insert'):
            self.reports.commit_report(candidate, parents, count_review(parents))

        reopened = ReportStore(self.workspace.center)
        self.assertEqual(self.center_counts(), before)
        self.assertEqual(fetch(self.workspace.center, 'SELECT id FROM reports WHERE id = ?', (candidate,)), [])
        self.assertEqual(fetch(self.workspace.center, 'SELECT report_id FROM report_receipts'), [(old.report_id,)])
        with self.assertRaises(LookupError):
            get_report(reopened, candidate)
        self.assertEqual(get_report(reopened, old.report_id), old)
