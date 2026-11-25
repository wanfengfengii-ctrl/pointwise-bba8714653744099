import argparse
import json
import sqlite3
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from intake.inbox_store import InboxStore
from intake.manifest import BatchManifest
from intake.receipts import receive_package
from issue.dispatch import freeze_package, get_package
from issue.issue_store import IssueStore, IssuedPackage
from links.catalog_store import CatalogStore
from links.fixed_list import freeze_links
from review.publication import get_report, issue_report
from review.report_store import ReportStore, SignedReport
from survey.capture import record_revision
from survey.revision_store import RevisionStore


@dataclass(frozen=True, slots=True)
class Workspace:
    root: Path

    @property
    def center(self) -> Path:
        return self.root / 'center.sqlite3'

    def station(self, name: str) -> Path:
        station_key = sha256(name.encode('utf-8')).hexdigest()
        return self.root / f'station-{station_key}.sqlite3'


def initialize_workspace(root: str | Path, manifests: Iterable[BatchManifest]) -> Workspace:
    workspace = Workspace(Path(root))
    workspace.root.mkdir(parents=True, exist_ok=True)
    manifests = tuple(manifests)
    inbox = InboxStore(workspace.center)
    inbox.initialize(manifests)
    CatalogStore(workspace.center).initialize()
    ReportStore(workspace.center).initialize()
    stations = {entry.station for manifest in manifests
                for entry in inbox.get_manifest(manifest.batch).stations}
    for name in sorted(stations):
        path = workspace.station(name)
        RevisionStore(path).initialize()
        IssueStore(path).initialize()
    return workspace


def _read_object(path: str | Path) -> dict:
    document = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(document, dict):
        raise ValueError('input document must contain a JSON object')
    return document


def _record_table(db: Path, survey: dict, table: str, parent_id: str | None = None) -> str:
    return record_revision(RevisionStore(db), survey['station'], survey['batch'], parent_id,
                           survey['terminals'], survey['tables'][table])


def _freeze(db: Path, station: str, revision: str) -> IssuedPackage:
    return freeze_package(RevisionStore(db), IssueStore(db), station, revision)


def _package_output(item: IssuedPackage, destination: Path) -> dict:
    destination.write_bytes(item.raw)
    return {'freeze_id': item.freeze_id, 'batch': item.batch, 'station': item.station,
            'revision_id': item.revision_id, 'path': str(destination)}


def _report_output(report: SignedReport) -> dict:
    result = asdict(report)
    result['total'] = str(Decimal(report.total))
    result['together'] = str(Decimal(report.together))
    result['receipt'] = json.loads(report.receipt)
    return result


def run_demo() -> dict:
    samples = Path(__file__).resolve().parents[1] / 'samples'
    settings = _read_object(samples / 'center.json')
    north = _read_object(samples / 'north.json')
    south = _read_object(samples / 'south.json')
    batch = settings['batch']
    manifest = BatchManifest.from_mapping(batch, settings['stations'])
    with TemporaryDirectory(prefix='wiring-review-') as directory:
        workspace = initialize_workspace(directory, (manifest,))
        north_path = workspace.station(north['station'])
        south_path = workspace.station(south['station'])
        original = _record_table(north_path, north, 'initial')
        corrected = _record_table(north_path, north, 'corrected', original)
        southern = _record_table(south_path, south, 'initial')
        star = _freeze(north_path, north['station'], original)
        chain = _freeze(north_path, north['station'], corrected)
        empty = _freeze(south_path, south['station'], southern)
        if get_package(IssueStore(north_path), star.freeze_id).raw != star.raw:
            raise RuntimeError('reissued station package changed bytes')

        inbox = InboxStore(workspace.center)
        catalog = CatalogStore(workspace.center)
        receipts = [receive_package(inbox, batch, item.station, item.raw) for item in (star, chain, empty)]
        list_id = freeze_links(inbox, catalog, batch, settings['links'])
        offline = workspace.root / 'offline'
        offline.mkdir()
        for path in (north_path, south_path):
            path.rename(offline / path.name)

        reports = ReportStore(workspace.center)
        results = {}
        cases = (
            ('star', (receipts[0], receipts[2]), (star, empty), (8, 3)),
            ('chain', (receipts[1], receipts[2]), (chain, empty), (4, 1)),
        )
        for label, receipt_ids, packages, expected in cases:
            report = issue_report(inbox, catalog, reports, receipt_ids, list_id, settings['selected'])
            reopened = get_report(ReportStore(workspace.center), report.report_id)
            actual_sources = tuple((item.receipt_id, item.freeze_id, item.revision_id, item.package_sha256)
                                   for item in reopened.parents)
            expected_sources = tuple((number, item.freeze_id, item.revision_id, sha256(item.raw).hexdigest())
                                     for number, item in zip(receipt_ids, packages, strict=True))
            if ((reopened.total, reopened.together) != expected or report != reopened
                    or actual_sources != expected_sources or reopened.list_id != list_id):
                raise RuntimeError(f'{label} report counts or frozen provenance did not match')
            results[label] = _report_output(reopened)
        if north_path.exists() or south_path.exists():
            raise RuntimeError('a station database was opened during the offline review')
        return results


def _init(args: argparse.Namespace) -> dict:
    settings = _read_object(args.manifest)
    manifest = BatchManifest.from_mapping(settings['batch'], settings['stations'])
    workspace = initialize_workspace(args.directory, (manifest,))
    actual = InboxStore(workspace.center).get_manifest(manifest.batch)
    return {'center': str(workspace.center),
            'stations': {entry.station: str(workspace.station(entry.station)) for entry in actual.stations}}


def _record(args: argparse.Namespace) -> dict:
    return {'revision_id': _record_table(args.db, _read_object(args.survey), args.table, args.parent)}


def _issue(args: argparse.Namespace) -> dict:
    return _package_output(_freeze(args.db, args.station, args.revision), args.output)


def _reissue(args: argparse.Namespace) -> dict:
    return _package_output(get_package(IssueStore(args.db), args.freeze_id), args.output)


def _receive(args: argparse.Namespace) -> dict:
    receipt_id = receive_package(InboxStore(args.db), args.batch, args.station, args.package.read_bytes())
    return {'receipt_id': receipt_id}


def _links(args: argparse.Namespace) -> dict:
    settings = _read_object(args.links)
    list_id = freeze_links(InboxStore(args.db), CatalogStore(args.db), settings['batch'], settings['links'])
    return {'list_id': list_id}


def _review(args: argparse.Namespace) -> dict:
    report = issue_report(InboxStore(args.db), CatalogStore(args.db), ReportStore(args.db),
                          args.receipts, args.list_id, args.selected)
    return _report_output(report)


def _get(args: argparse.Namespace) -> dict:
    return _report_output(get_report(ReportStore(args.db), args.report_id))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Offline electrical wiring review')
    commands = parser.add_subparsers(dest='action', required=True)
    init = commands.add_parser('init', help='initialize a workspace and batch manifest')
    init.add_argument('directory', type=Path)
    init.add_argument('manifest', type=Path)
    init.set_defaults(handler=_init)

    record = commands.add_parser('record', help='record a survey revision')
    record.add_argument('db', type=Path)
    record.add_argument('survey', type=Path)
    record.add_argument('--table', default='initial')
    record.add_argument('--parent')
    record.set_defaults(handler=_record)

    freeze = commands.add_parser('freeze', help='issue a frozen station package')
    freeze.add_argument('db', type=Path)
    freeze.add_argument('station')
    freeze.add_argument('revision')
    freeze.add_argument('output', type=Path)
    freeze.set_defaults(handler=_issue)

    reissue = commands.add_parser('reissue', help='retrieve original station package bytes')
    reissue.add_argument('db', type=Path)
    reissue.add_argument('freeze_id')
    reissue.add_argument('output', type=Path)
    reissue.set_defaults(handler=_reissue)

    receive = commands.add_parser('receive', help='receive a station package')
    receive.add_argument('db', type=Path)
    receive.add_argument('batch')
    receive.add_argument('station')
    receive.add_argument('package', type=Path)
    receive.set_defaults(handler=_receive)

    links = commands.add_parser('links', help='freeze a cross-link list')
    links.add_argument('db', type=Path)
    links.add_argument('links', type=Path)
    links.set_defaults(handler=_links)

    review = commands.add_parser('review', help='issue an offline report')
    review.add_argument('db', type=Path)
    review.add_argument('receipts', nargs=2)
    review.add_argument('list_id')
    review.add_argument('selected', nargs=2)
    review.set_defaults(handler=_review)

    get = commands.add_parser('get', help='retrieve an original report and receipt')
    get.add_argument('db', type=Path)
    get.add_argument('report_id')
    get.set_defaults(handler=_get)

    demo = commands.add_parser('demo', help='run the sample shift in a temporary workspace')
    demo.set_defaults(handler=lambda _args: run_demo())
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except (ValueError, LookupError, OSError, sqlite3.Error) as error:
        parser.exit(2, f'{error}\n')
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
