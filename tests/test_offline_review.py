import json
from hashlib import sha256

from intake.manifest import BatchManifest
from intake.receipts import receive_package
from review.publication import get_report
from review.report_store import ReportStore
from survey.capture import record_revision
from survey.revision_store import RevisionStore
from tests.support import (CHAIN_FORESTS, SPLIT, STAR_FORESTS, WorkspaceCase, enumerate_wirings,
                           independent_package, link)


class OfflineReviewTests(WorkspaceCase):
    def test_offline_star_and_chain_preserve_frozen_parents(self):
        star, chain, south = self.stage()
        star_id, chain_id, south_id = self.admit(star, chain, south)
        list_id = self.link_list()
        self.go_offline()
        actual_counts = []
        actual_bindings = []
        cases = ((star, star_id, 'initial', [1, 2, 2, 3]), (chain, chain_id, 'corrected', [1, 1, 1, 1]))
        for north, receipt_id, table, expected_bins in cases:
            raw_tables = {'north': self.north['tables'][table], 'south': self.south['tables']['initial']}
            bins = enumerate_wirings(self.terminals, raw_tables, self.settings['links'], ('p', 'q'))
            self.assertEqual(bins, expected_bins)
            report = self.publish((receipt_id, south_id), list_id)
            self.assertEqual((report.total, report.together), (sum(expected_bins), expected_bins[3]))
            for parent, item, expected_id in zip(report.parents, (north, south), (receipt_id, south_id), strict=True):
                self.assertEqual((parent.receipt_id, parent.freeze_id, parent.revision_id, parent.station),
                                 (expected_id, item.freeze_id, item.revision_id, item.station))
                self.assertEqual(parent.package_sha256, sha256(item.raw).hexdigest())
            reopened = get_report(ReportStore(self.workspace.center), report.report_id)
            self.assertEqual(reopened, report)
            self.assertEqual(reopened.list_id, list_id)
            actual_counts.append([reopened.total, reopened.together])
            actual_bindings.append([reopened.parents[0].freeze_id, reopened.parents[1].freeze_id, reopened.list_id])
        self.assertEqual(self.center_counts(), (3, 1, 2, 2))
        for station in ('north', 'south'):
            self.assertFalse(self.workspace.station(station).exists())
        marker = {
            'case_id': 'v6',
            'input': {'north': self.north['tables'], 'south': self.south['tables']['initial'],
                      'links': self.settings['links'], 'selected': ['p', 'q']},
            'expected': [[8, 3], [4, 1]], 'actual': actual_counts,
            'downstream_expected': [[star.freeze_id, south.freeze_id, list_id],
                                    [chain.freeze_id, south.freeze_id, list_id]],
            'downstream_actual': actual_bindings,
            'code_paths': ['survey/capture.py', 'issue/contributions.py', 'issue/dispatch.py',
                           'intake/inbox_store.py', 'links/fixed_list.py', 'review/counting.py',
                           'review/publication.py', 'review/report_store.py'],
            'oracle': '原始线身份子集按顶点数减一取边并独立遍历检验连通，按两线使用情况分四栏。',
        }
        print('POINTWISE_SCENARIO ' + json.dumps(marker, ensure_ascii=False, sort_keys=True))

    def test_independently_authored_packages_are_sufficient(self):
        self.go_offline()
        south_raw = independent_package(self.batch, 'south', 'external-s', 's-revision', [(SPLIT, 1)],
                                        ('C', 'A', 'B'))
        south = receive_package(self.inbox, self.batch, 'south', south_raw)
        list_id = self.link_list()
        for label, forests, expected in (('star', STAR_FORESTS, (8, 3)), ('chain', CHAIN_FORESTS, (4, 1))):
            with self.subTest(label=label):
                north_raw = independent_package(self.batch, 'north', f'external-{label}', label, forests)
                north = receive_package(self.inbox, self.batch, 'north', north_raw)
                report = self.publish((north, south), list_id)
                self.assertEqual((report.total, report.together), expected)
                self.assertEqual([entry.freeze_id for entry in report.parents], [f'external-{label}', 'external-s'])
                self.assertEqual(report.list_id, list_id)

    def test_parallel_alternatives_and_disconnected_zero(self):
        _, chain, south = self.stage()
        ab_only = {'junctions': [], 'wires': [['base-ab', 'A', 'B']]}
        revision = record_revision(RevisionStore(self.workspace.station('north')), 'north', self.batch,
                                   chain.revision_id, self.terminals, ab_only)
        broken = self.freeze('north', revision)
        chain_id, broken_id, south_id = self.admit(chain, broken, south)
        rows = [link('p', 'A', 'B'), link('q', 'B', 'A')]
        list_id = self.link_list(rows)
        self.go_offline()
        for north_id, table, bins in ((chain_id, self.north['tables']['corrected'], [1, 1, 1, 0]),
                                      (broken_id, ab_only, [0, 0, 0, 0])):
            with self.subTest(bins=bins):
                self.assertEqual(enumerate_wirings(self.terminals, {'north': table,
                                 'south': self.south['tables']['initial']}, rows, ('p', 'q')), bins)
                report = self.publish((north_id, south_id), list_id)
                self.assertEqual((report.total, report.together), (sum(bins), 0))
                self.assertTrue(report.receipt)
                self.assertEqual(get_report(self.reports, report.report_id), report)

    def test_raw_oracle_covers_two_private_networks_loops_and_extra_links(self):
        north_table = self.north['tables']['initial']
        south_table = {'junctions': ['junction-n17'], 'wires': [
            ['n-arm-a', 'A', 'junction-n17'], ['s-arm-c', 'C', 'junction-n17'],
            ['s-ac-1', 'A', 'C'], ['s-ac-2', 'C', 'A'], ['s-loop', 'C', 'C'],
        ]}
        south_rev = record_revision(RevisionStore(self.workspace.station('south')), 'south', self.batch,
                                     None, self.terminals, south_table)
        north = self.freeze('north', self.record('north'))
        south = self.freeze('south', south_rev)
        ids = self.admit(north, south)
        rows = self.settings['links'] + [link('r', 'A', 'C'), link('loop', 'A', 'A')]
        list_id = self.link_list(rows)
        self.go_offline()
        for selected in (('p', 'q'), ('r', 'q'), ('loop', 'p')):
            with self.subTest(selected=selected):
                bins = enumerate_wirings(self.terminals, {'north': north_table, 'south': south_table}, rows, selected)
                report = self.publish(ids, list_id, selected)
                self.assertGreater(sum(bins), 0)
                self.assertEqual((report.total, report.together), (sum(bins), bins[3]))
                if 'loop' in selected:
                    self.assertEqual(report.together, 0)

    def test_invalid_requests_leave_no_report_or_receipt(self):
        star, chain, south = self.stage()
        star_id, chain_id, south_id = self.admit(star, chain, south)
        other = BatchManifest.from_mapping('other-batch', self.settings['stations'])
        self.inbox.initialize((other,))
        other_id = receive_package(self.inbox, other.batch, 'south', independent_package(
            other.batch, 'south', 'other-freeze', 'other-rev', [(SPLIT, 1)]))
        list_id = self.link_list()
        self.go_offline()
        for ids, list_number, selected, error in (
            ((star_id, star_id), list_id, ('p', 'q'), ValueError),
            ((star_id, chain_id), list_id, ('p', 'q'), ValueError),
            ((star_id, other_id), list_id, ('p', 'q'), ValueError),
            ((star_id, south_id), list_id, ('p', 'p'), ValueError),
            ((star_id, south_id), list_id, ('p', 'other'), ValueError),
            ((star_id, 'missing'), list_id, ('p', 'q'), LookupError),
            ((star_id, south_id), 'missing', ('p', 'q'), LookupError),
        ):
            with self.subTest(ids=ids, list_id=list_number, selected=selected), self.assertRaises(error):
                self.publish(ids, list_number, selected)
        self.assertEqual(self.center_counts(), (4, 1, 0, 0))

    def test_large_counts_remain_exact_on_reopen(self):
        self.go_offline()
        count = 1 << 16000
        north = independent_package(self.batch, 'north', 'many-parallel', 'large-rev',
                                    [(SPLIT, 1), ((('A', 'B'), ('C',)), count)])
        south = independent_package(self.batch, 'south', 'large-south', 'empty-rev', [(SPLIT, 1)])
        ids = (receive_package(self.inbox, self.batch, 'north', north),
               receive_package(self.inbox, self.batch, 'south', south))
        report = self.publish(ids, self.link_list())
        reopened = get_report(ReportStore(self.workspace.center), report.report_id)
        self.assertTrue(reopened.total == count + 1)
        self.assertEqual(reopened.together, 1)
        self.assertEqual(reopened.receipt, report.receipt)
