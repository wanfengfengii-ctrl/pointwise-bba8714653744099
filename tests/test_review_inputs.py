import json

from intake.manifest import BatchManifest
from intake.receipts import receive_package
from tests.support import WorkspaceCase, fetch, link


class ReviewInputTests(WorkspaceCase):
    def test_retries_use_original_receipt_and_distinct_freezes_get_distinct_receipts(self):
        star, chain, _ = self.stage()
        first, second, repeated = self.admit(star, chain, star)
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, second)
        for receipt_id, package in ((first, star), (second, chain)):
            result = self.inbox.find_receipt(receipt_id)
            self.assertEqual(result.raw, package.raw)
            self.assertEqual(result.envelope.freeze_id, package.freeze_id)
            self.assertEqual(result.envelope.revision_id, package.revision_id)
        self.assertEqual(self.center_counts(), (2, 0, 0, 0))

    def test_same_freeze_with_changed_bytes_or_source_is_rejected(self):
        star, _, _ = self.stage()
        first, = self.admit(star)
        document = json.loads(star.raw)
        changed_parent = {**document, 'revision_id': 'another-parent'}
        changed_station = {**document, 'station': 'south'}
        for station, raw in (('north', star.raw + b'\n'),
                             ('north', json.dumps(changed_parent).encode()),
                             ('south', json.dumps(changed_station).encode())):
            with self.subTest(station=station, raw=raw):
                with self.assertRaisesRegex(ValueError, 'already bound'):
                    receive_package(self.inbox, self.batch, station, raw)
        self.assertEqual(self.inbox.find_receipt(first).raw, star.raw)
        self.assertEqual(self.center_counts(), (1, 0, 0, 0))

    def test_wrong_station_wrong_batch_wrong_terminals_and_bad_package_do_not_enter(self):
        star, _, _ = self.stage()
        other = BatchManifest.from_mapping('other-batch', self.settings['stations'])
        self.inbox.initialize((other,))
        with self.assertRaises(ValueError):
            receive_package(self.inbox, self.batch, 'south', star.raw)
        with self.assertRaises(ValueError):
            receive_package(self.inbox, other.batch, 'north', star.raw)
        document = json.loads(star.raw)
        malformed = [b'{', b'\xff', b'{"version":1,"version":1}',
                     json.dumps({**document, 'version': True}).encode(),
                     json.dumps({key: val for key, val in document.items() if key != 'revision_id'}).encode()]
        malformed.extend(json.dumps({**document, 'evidence': {'forests': rows}}).encode()
                         for rows in (
                             [{'groups': [['A', 'B'], ['B']], 'count': '0x1'}],
                             [{'groups': [['A', 'B', 'C']], 'count': '0x0'}],
                             [{'groups': [['A', 'B'], ['C']], 'count': '0x1'},
                              {'groups': [['C'], ['B', 'A']], 'count': '0x2'}],
                         ))
        different = {**document, 'terminals': ['A', 'B', 'Z'], 'evidence': {
            'forests': [{'groups': [['A'], ['B'], ['Z']], 'count': '0x1'}]}}
        for raw in (*malformed, json.dumps(different).encode()):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                receive_package(self.inbox, self.batch, 'north', raw)
        self.assertEqual(self.center_counts(), (0, 0, 0, 0))
        self.assertEqual(len(self.admit(star)), 1)

    def test_parallel_links_keep_identity_and_corrected_list_has_its_own_number(self):
        rows = [link('p', 'A', 'B'), {'id': 'q', 'a': ['south', 'B'], 'b': ['north', 'A']}]
        original_id = self.link_list(rows)
        original = self.catalog.find_list(original_id)
        self.assertEqual([edge.to_row() for edge in original.links], rows)
        corrected_id = self.link_list([link('p', 'A', 'B'), link('q', 'B', 'C')])
        self.assertNotEqual(corrected_id, original_id)
        self.assertEqual(self.catalog.find_list(original_id), original)
        self.assertEqual(self.catalog.find_list(corrected_id).links[1].b.terminal, 'C')
        for bad in ([link('p', 'A', 'B'), link('p', 'B', 'C')],
                    [link('p', 'A', 'unknown')],
                    [{'id': 'p', 'a': ['third', 'A'], 'b': ['south', 'B']}]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.link_list(bad)
        self.assertEqual(fetch(self.workspace.center, 'SELECT COUNT(*) FROM link_lists'), [(2,)])
        self.assertEqual(self.catalog.find_list(original_id), original)
