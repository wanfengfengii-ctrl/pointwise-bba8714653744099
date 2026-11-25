from uuid import uuid4

from intake.inbox_store import InboxStore
from links.catalog_store import CatalogStore
from review.counting import count_review
from review.parents import bind_review_parents
from review.report_store import ReportStore, SignedReport
from review.request import validate_request
from survey.terminals import validate_name


def issue_report(
    inbox: InboxStore, catalog: CatalogStore, reports: ReportStore,
    receipt_ids: object, list_id: str, selected: object,
) -> SignedReport:
    request = validate_request(receipt_ids, list_id, selected)
    parents = bind_review_parents(inbox, catalog, request)
    counts = count_review(parents)
    return reports.commit_report(f'report-{uuid4().hex}', parents, counts)


def get_report(reports: ReportStore, report_id: str) -> SignedReport:
    report = reports.find_report(validate_name(report_id, 'report number'))
    if report is None:
        raise LookupError(f'unknown report: {report_id}')
    return report
