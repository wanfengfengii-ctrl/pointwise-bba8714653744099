import json

from issue.contributions import count_local_contributions
from review.counting import count_review
from review.parents import bind_review_parents
from review.request import validate_request
from survey.capture import record_revision
from survey.revision_store import RevisionStore
from tests.support import (CHAIN_FORESTS, SPLIT, STAR_FORESTS, WorkspaceCase,
                           independent_package, link)


class ForestEvidenceTests(WorkspaceCase):
    def test_local_evidence_keeps_every_forest_partition(self):
        original = record_revision(RevisionStore(self.workspace.station('north')), 'north',
                                   self.batch, None, self.terminals, self.north['tables']['initial'])
        corrected = record_revision(RevisionStore(self.workspace.station('north')), 'north',
                                    self.batch, original, self.terminals, self.north['tables']['corrected'])
        star = dict(count_local_contributions(
            RevisionStore(self.workspace.station('north')).get_revision(original)).forests)
        chain = dict(count_local_contributions(
            RevisionStore(self.workspace.station('north')).get_revision(corrected)).forests)
        # The frozen body must carry every acyclic selection, not only the fewest-group one.
        self.assertEqual(star, dict(STAR_FORESTS))
        self.assertEqual(chain, dict(CHAIN_FORESTS))
        self.assertGreater(len(star), 1)

    def test_frozen_body_is_sufficient_for_offline_counting(self):
        star, chain, south = self.stage()
        star_id, chain_id, south_id = self.admit(star, chain, south)
        list_id = self.link_list()
        self.go_offline()
        # Re-derive each station's forest evidence from the frozen bytes alone.
        from issue.envelope import decode_package
        frozen = decode_package(star.raw)
        self.assertEqual(dict(frozen.evidence.forests), dict(STAR_FORESTS))
        self.assertIn(SPLIT, dict(frozen.evidence.forests))
        self.assertEqual(json.loads(star.raw)['version'], 1)
        for receipt_ids, expected in (((star_id, south_id), (8, 3)), ((chain_id, south_id), (4, 1))):
            report = self.publish(receipt_ids, list_id)
            self.assertEqual((report.total, report.together), expected)

    def test_two_station_parallel_split_needs_more_links_than_budget(self):
        # Both stations expose the same A-B / C split; the fixed list only offers
        # A-B links, so the edge budget can never join C: no usable plan.
        forests = [((('A', 'B'), ('C',)), 1)]
        north = self.admit_package('north', 'split-n', independent_package(
            self.batch, 'north', 'split-n', 's-rev', forests))
        south = self.admit_package('south', 'split-s', independent_package(
            self.batch, 'south', 'split-s', 's-rev', forests))
        rows = [link('p', 'A', 'B'), link('q', 'B', 'A')]
        list_id = self.link_list(rows)
        request = validate_request((north, south), list_id, ('p', 'q'))
        counts = count_review(bind_review_parents(self.inbox, self.catalog, request))
        self.assertEqual((counts.total, counts.together), (0, 0))

    def admit_package(self, station, freeze_id, raw):
        from intake.receipts import receive_package
        return receive_package(self.inbox, self.batch, station, raw)
