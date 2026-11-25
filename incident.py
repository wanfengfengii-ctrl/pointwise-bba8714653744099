import json
import unittest
from hashlib import sha256

from intake.receipts import receive_package
from review.publication import get_report
from review.report_store import ReportStore
from tests.support import SPLIT, STAR_FORESTS, WorkspaceCase, independent_package


class WiringIncident(WorkspaceCase):
    def test_counts_and_original_receipts_after_station_shutdown(self):
        star, chain, south = self.stage()
        star_id, chain_id, south_id = self.admit(star, chain, south)
        list_id = self.link_list()
        self.go_offline()

        def receive(station, label, forests, terminals=("A", "B", "C")):
            raw = independent_package(self.batch, station, f"incident-{label}",
                                      f"external-{label}", forests, terminals)
            return receive_package(self.inbox, self.batch, station, raw)

        external_star = receive("north", "star", STAR_FORESTS)
        external_south = receive("south", "empty", [(SPLIT, 1)], ("C", "A", "B"))
        ab = ( ("A", "B"), ("C",) )
        ab_forests = [(SPLIT, 1), (ab, 1)]
        overlap = (receive("north", "ab-north", ab_forests),
                   receive("south", "ab-south", ab_forests))
        cases = (
            ("star", (star_id, south_id), (8, 3)),
            ("chain", (chain_id, south_id), (4, 1)),
            ("independent_star", (external_star, external_south), (8, 3)),
            ("overlapping_ab", overlap, (3, 1)),
        )
        expected = {label: counts for label, _, counts in cases}
        observed = {}
        for label, ids, _ in cases:
            signed = self.publish(ids, list_id)
            reopened = get_report(ReportStore(self.workspace.center), signed.report_id)
            self.assertEqual(reopened, signed)
            self.assertEqual(reopened.list_id, list_id)
            self.assertEqual(tuple(parent.receipt_id for parent in reopened.parents), ids)
            digests = tuple(sha256(self.inbox.find_receipt(number).raw).hexdigest() for number in ids)
            self.assertEqual(tuple(parent.package_sha256 for parent in reopened.parents), digests)
            observed[label] = (reopened.total, reopened.together)

        for station in ("north", "south"):
            self.assertFalse(self.workspace.station(station).exists())
        if observed != expected:
            print("WIRING_PLAN_COUNTS_MISMATCH " + json.dumps({"actual": observed, "expected": expected},
                                                            sort_keys=True), flush=True)
        else:
            print(json.dumps({"verified_counts": observed}, sort_keys=True), flush=True)
        self.assertEqual(observed, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
